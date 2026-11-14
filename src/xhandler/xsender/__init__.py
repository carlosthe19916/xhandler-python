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

from xhandler._core import invoke
from xhandler.xsender.models import (
    BILL_CONSULT_SERVICE_URL,
    BILL_VALID_SERVICE_URL,
    Cdr,
    ConsultDocument,
    ConsultResult,
    ConsultStatus,
    Credentials,
    Fault,
    File,
    NoCdr,
    SendResult,
    Status,
    Target,
    Urls,
    ValidateCdp,
    VerifyResult,
)

__all__ = [
    "BILL_CONSULT_SERVICE_URL",
    "BILL_VALID_SERVICE_URL",
    "Cdr",
    "ConsultDocument",
    "ConsultResult",
    "ConsultStatus",
    "Credentials",
    "Fault",
    "File",
    "FileSender",
    "NoCdr",
    "SendResult",
    "Status",
    "SunatClient",
    "Target",
    "Urls",
    "ValidateCdp",
    "VerifyResult",
]


class SunatClient:
    """Sends the requests to SUNAT and keeps the OAuth tokens of the guias de
    remision. Share one between the FileSenders of several companies."""

    def __init__(self, http: httpx.Client | None = None) -> None:
        """``http`` defaults to a client with a 30s connection timeout and a
        120s timeout for the rest."""
        self._http = http or httpx.Client(timeout=httpx.Timeout(120, connect=30))
        self._lock = threading.Lock()
        self._tokens: dict[str, tuple[str, float]] = {}

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

    def validate_cdp(self, url: str, cdp: ValidateCdp, credentials: Credentials) -> ConsultResult:
        """billValidService validaCDPcriterios."""
        call = {"validate_cdp": {"url": url, "cdp": _json(cdp)}}
        return ConsultResult.model_validate(self._exchange(call, False, credentials))

    def validate_file(self, url: str, file: File, credentials: Credentials) -> ConsultResult:
        """billValidService verificaCPEarchivo."""
        call = {"validate_file": {"url": url, "file": _json(file)}}
        return ConsultResult.model_validate(self._exchange(call, False, credentials))

    def _exchange(self, call: Any, rest: bool, credentials: Credentials) -> Any:
        """Sends a call and returns its answer. A REST call first gets a token;
        a token SUNAT rejects (HTTP 401) is forgotten."""
        token = self._token(credentials) if rest else None
        request = invoke(
            "request", {"call": call, "credentials": _json(credentials), "token": token}
        )
        response = self._send(request)
        if rest and response.status_code == 401:
            self._forget(credentials)
        return invoke(
            "parse", {"call": call, "status": response.status_code, "body": response.text}
        )

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
        except httpx.ConnectError:
            return send()  # once more when the connection failed

    def _token(self, credentials: Credentials) -> str:
        """A cached token, reused until a minute before it expires, or a new one."""
        key = _token_key(credentials)
        with self._lock:
            cached = self._tokens.get(key)
        if cached and time.monotonic() < cached[1]:
            return cached[0]
        token = self._exchange("token", False, credentials)["token"]
        with self._lock:
            reuse_before = time.monotonic() + max(token["expires_in"] - 60, 0)
            self._tokens[key] = (token["access_token"], reuse_before)
        return str(token["access_token"])

    def _forget(self, credentials: Credentials) -> None:
        with self._lock:
            self._tokens.pop(_token_key(credentials), None)


def _token_key(credentials: Credentials) -> str:
    return f"{credentials.client_id or ''}:{credentials.username}"


def _json(model: Any) -> Any:
    return model.model_dump(mode="json")


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


_default_client: SunatClient | None = None


class FileSender:
    """Sends the signed documents of one company. The document decides
    everything else: the file name, the service and the operation."""

    def __init__(
        self, urls: Urls, credentials: Credentials, client: SunatClient | None = None
    ) -> None:
        self.urls = urls
        self.credentials = credentials
        self._client = client

    @property
    def client(self) -> SunatClient:
        global _default_client
        if self._client is None:
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
