"""Sends signed UBL documents to SUNAT: the SOAP services (billService,
consult and validation) and the REST API of the guias de remision with its
OAuth token.

The xhandler core builds every request and reads every answer (CDR, tickets,
faults); this package only sends them over HTTP with httpx.
"""

from __future__ import annotations

import base64
import threading
import time
from typing import Any

import httpx

from xhandler._core import ErrorKind, XhandlerError, invoke
from xhandler.xsender.models import (
    BILL_CONSULT_SERVICE_URL,
    BILL_VALID_SERVICE_URL,
    CDR,
    ConsultDocument,
    ConsultResult,
    ConsultStatus,
    Credentials,
    Fault,
    File,
    NoCDR,
    SendResult,
    Status,
    Target,
    URLs,
    ValidateCDP,
    VerifyResult,
)

__all__ = [
    "BILL_CONSULT_SERVICE_URL",
    "BILL_VALID_SERVICE_URL",
    "CDR",
    "ConsultDocument",
    "ConsultResult",
    "ConsultStatus",
    "Credentials",
    "Fault",
    "File",
    "FileSender",
    "NoCDR",
    "SendResult",
    "Status",
    "SunatClient",
    "Target",
    "URLs",
    "ValidateCDP",
    "VerifyResult",
]


_RATE_LIMIT_PAUSES = (1, 2)
"""Seconds before retrying a request SUNAT's front proxy refused."""


class SunatClient:
    """Sends the requests to SUNAT and keeps the OAuth tokens of the guias de
    remision. Share one between the FileSenders of several companies."""

    def __init__(
        self, http: httpx.Client | None = None, security_api_url: str | None = None
    ) -> None:
        """``http`` defaults to a client with a 30s connection timeout and a
        120s timeout for the rest. ``security_api_url`` is where the tokens of
        the guias are requested (SUNAT's by default)."""
        self._http = http or httpx.Client(timeout=httpx.Timeout(120, connect=30))
        self._security_api_url = security_api_url
        self._lock = threading.Lock()  # guards _tokens
        self._tokens: dict[str, tuple[str, float]] = {}
        # Held while a token is requested, so concurrent calls don't revoke
        # each other's tokens
        self._requesting = threading.Lock()

    def close(self) -> None:
        """Closes the HTTP connections."""
        self._http.close()

    def __enter__(self) -> SunatClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def get_status(
        self, url: str, document: ConsultDocument, credentials: Credentials
    ) -> ConsultResult:
        """billConsultService getStatus: the status of a document already sent."""
        call = {"get_status": {"url": url, "document": _json(document)}}
        return ConsultResult.model_validate(self._exchange(call, False, credentials))

    def get_status_cdr(
        self, url: str, document: ConsultDocument, credentials: Credentials
    ) -> ConsultResult:
        """billConsultService getStatusCdr: the CDR of a document already sent."""
        call = {"get_status_cdr": {"url": url, "document": _json(document)}}
        return ConsultResult.model_validate(self._exchange(call, False, credentials))

    def validate_cdp(self, url: str, cdp: ValidateCDP, credentials: Credentials) -> ConsultResult:
        """billValidService validaCDPcriterios."""
        call = {"validate_cdp": {"url": url, "cdp": _json(cdp)}}
        return ConsultResult.model_validate(self._exchange(call, False, credentials))

    def validate_file(self, url: str, file: File, credentials: Credentials) -> ConsultResult:
        """billValidService verificaCPEarchivo."""
        call = {"validate_file": {"url": url, "file": _json(file)}}
        return ConsultResult.model_validate(self._exchange(call, False, credentials))

    def _exchange(self, call: Any, rest: bool, credentials: Credentials) -> Any:
        """Sends a call and returns its answer. SUNAT revokes the tokens of the
        guias before they expire: a REST call rejected with HTTP 401 is retried
        once with a new token. A SOAP call refused by SUNAT's rate limiting is
        retried after a pause."""
        if rest:
            token = self._token(credentials)
            response = self._send(self._request(call, credentials, token))
            if response.status_code == 401 and credentials.token is None:
                self._forget(credentials, token)
                response = self._send(self._request(call, credentials, self._token(credentials)))
            return _parse(call, response)

        request = self._request(call, credentials, None)
        for pause in (*_RATE_LIMIT_PAUSES, None):
            try:
                return _parse(call, self._send(request))
            except XhandlerError as error:
                if error.kind is not ErrorKind.RATE_LIMITED or pause is None:
                    raise
                time.sleep(pause)

    @staticmethod
    def _request(call: Any, credentials: Credentials, token: str | None) -> Any:
        return invoke("request", {"call": call, "credentials": _json(credentials), "token": token})

    def _send(self, request: dict[str, Any]) -> httpx.Response:
        def send() -> httpx.Response:
            return self._http.request(
                request["method"],
                request["url"],
                headers=dict(request["headers"]),
                content=request["body"],
            )

        try:
            return send()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return send()  # once more: the request never reached SUNAT

    def _token(self, credentials: Credentials) -> str:
        """The token of the credentials, a cached one (reused until a minute
        before it expires), or a new one."""
        if credentials.token is not None:
            return credentials.token
        key = _token_key(credentials)
        cached = self._cached_token(key)
        if cached:
            return cached
        with self._requesting:
            cached = self._cached_token(key)
            if cached:
                return cached
            return self._request_token(key, credentials)

    def _cached_token(self, key: str) -> str | None:
        with self._lock:
            cached = self._tokens.get(key)
        return cached[0] if cached and time.monotonic() < cached[1] else None

    def _request_token(self, key: str, credentials: Credentials) -> str:
        call = {"token": {"url": self._security_api_url}}
        token = self._exchange(call, False, credentials)["token"]
        with self._lock:
            reuse_before = time.monotonic() + max(token["expires_in"] - 60, 0)
            self._tokens[key] = (token["access_token"], reuse_before)
        return str(token["access_token"])

    def _forget(self, credentials: Credentials, rejected: str) -> None:
        """Forgets the rejected token, unless another call already replaced it."""
        key = _token_key(credentials)
        with self._lock:
            if self._tokens.get(key, ("",))[0] == rejected:
                del self._tokens[key]


def _parse(call: Any, response: httpx.Response) -> Any:
    return invoke(
        "parse",
        {
            "call": call,
            "status": response.status_code,
            "headers": list(response.headers.multi_items()),
            "body": response.text,
        },
    )


def _token_key(credentials: Credentials) -> str:
    return f"{credentials.client_id or ''}:{credentials.username}"


def _json(model: Any) -> Any:
    return model.model_dump(mode="json")


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


_default_client: SunatClient | None = None
_default_client_lock = threading.Lock()


class FileSender:
    """Sends the signed documents of one company. The document decides
    everything else: the file name, the service and the operation."""

    def __init__(
        self, urls: URLs, credentials: Credentials, client: SunatClient | None = None
    ) -> None:
        self.urls = urls
        self.credentials = credentials
        self._client = client

    @property
    def client(self) -> SunatClient:
        global _default_client
        if self._client is None:
            with _default_client_lock:
                _default_client = _default_client or SunatClient()
            self._client = _default_client
        return self._client

    def send_file(self, xml: bytes | str) -> SendResult:
        """Zips the signed XML and sends it to its SUNAT service."""
        prepared = invoke("prepare_send_file", {"xml": _b64(_bytes(xml)), "urls": _json(self.urls)})
        return self._send(prepared)

    def send_pack(self, name: str, files: list[bytes | str]) -> SendResult:
        """Sends several invoices in one zip called ``name`` (sendPack)."""
        prepared = invoke(
            "prepare_send_pack",
            {"name": name, "files": [_b64(_bytes(f)) for f in files], "urls": _json(self.urls)},
        )
        return self._send(prepared)

    def _send(self, prepared: dict[str, Any]) -> SendResult:
        target = prepared["send_target"]
        call = {"send_file": {"target": target, "file": prepared["file"]}}
        answer = self.client._exchange(call, target["protocol"] == "rest", self.credentials)
        return SendResult.model_validate(
            {
                **answer,
                "send_target": target,
                "verify_ticket_target": prepared["verify_ticket_target"],
            }
        )

    def verify_ticket(self, target: Target, ticket: str) -> VerifyResult:
        """Asks the service ``target`` for the status of a ticket."""
        call = {"verify_ticket": {"target": _json(target), "ticket": ticket}}
        answer = self.client._exchange(call, target.protocol == "rest", self.credentials)
        return VerifyResult.model_validate(answer)

    def verify_file_ticket(self, xml: bytes | str, ticket: str) -> VerifyResult:
        """:meth:`verify_ticket` with the service of the sent document."""
        target = invoke(
            "verify_ticket_target", {"xml": _b64(_bytes(xml)), "urls": _json(self.urls)}
        )
        return self.verify_ticket(Target.model_validate(target), ticket)


def _bytes(xml: bytes | str) -> bytes:
    return xml.encode() if isinstance(xml, str) else xml
