"""Inputs and answers of the SUNAT services."""

from __future__ import annotations

import base64
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer


def _from_base64(value: object) -> object:
    return base64.b64decode(value) if isinstance(value, str) else value


Bytes = Annotated[
    bytes,
    BeforeValidator(_from_base64),
    PlainSerializer(lambda b: base64.b64encode(b).decode(), return_type=str, when_used="json"),
]
"""Raw bytes in Python, base64 in the JSON of the core."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Urls(_Model):
    """The SUNAT services where a company sends its documents."""

    invoice: str
    perception_retention: str
    despatch: str = ""
    """The REST API of the guias de remision; SUNAT has no beta for it."""

    @classmethod
    def beta(cls) -> Urls:
        """SUNAT beta (testing) services; without guias de remision."""
        return cls(
            invoice="https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService",
            perception_retention="https://e-beta.sunat.gob.pe/ol-ti-itemision-otroscpe-gem-beta/billService",
        )

    @classmethod
    def production(cls) -> Urls:
        """SUNAT production services."""
        return cls(
            invoice="https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService",
            perception_retention="https://e-factura.sunat.gob.pe/ol-ti-itemision-otroscpe-gem/billService",
            despatch="https://api-cpe.sunat.gob.pe/v1/contribuyente/gem",
        )


BILL_CONSULT_SERVICE_URL = "https://e-factura.sunat.gob.pe/ol-it-wsconscpegem/billConsultService"
"""Looks up documents already sent (get_status, get_status_cdr)."""
BILL_VALID_SERVICE_URL = "https://e-factura.sunat.gob.pe/ol-it-wsconsvalidcpe/billValidService"
"""Validates documents (validate_cdp, validate_file)."""


class Credentials(_Model):
    """Credentials of the company."""

    username: str
    """SOL user, e.g. "20123456789MODDATOS"."""
    password: str
    client_id: str | None = None
    """API client of the REST services (guias de remision), from SUNAT's SOL menu."""
    client_secret: str | None = None

    def __repr__(self) -> str:
        return f"Credentials(username={self.username!r}, <secrets redacted>)"


class Target(_Model):
    """A SUNAT service for a file or a ticket."""

    protocol: Literal["soap", "rest"]
    url: str
    action: Literal["bill", "summary", "pack"] | None = None
    """The operation of the SOAP files."""


class File(_Model):
    """A zip for SUNAT."""

    filename: str
    zip: Bytes


class ConsultDocument(_Model):
    """A document already sent to SUNAT."""

    ruc: str
    tipo_comprobante: str
    """Catalog1, e.g. "01"."""
    serie: str
    numero: int


class ValidateCdp(ConsultDocument):
    """The criteria of validaCDPcriterios."""

    tipo_documento_identidad_receptor: str
    """Catalog6."""
    numero_documento_identidad_receptor: str
    fecha_emision: str
    """dd/MM/yyyy."""
    importe_total: str
    numero_autorizacion: str | None = None


class Status(str, Enum):
    """The SUNAT verdict of a document."""

    ACCEPTED = "ACEPTADO"
    REJECTED = "RECHAZADO"
    EXCEPTION = "EXCEPCION"
    IN_PROGRESS = "EN_PROCESO"
    UNKNOWN = "UNKNOWN"


class Cdr(_Model):
    """The receipt SUNAT gives back (Constancia de Recepcion)."""

    zip: Bytes
    response_code: str
    description: str
    notes: list[str]
    status: Status
    status_code: str | None = None
    """The ticket status, only when verifying a ticket."""


class Fault(_Model):
    """An error answered by SUNAT, e.g. "soap-env:Client.0111"."""

    code: str
    message: str
    status: Status


class NoCdr(_Model):
    """A ticket status without CDR, e.g. "98" (in progress)."""

    status_code: str
    status: Status


class SendResult(_Model):
    """The answer to a sent file: a CDR, a ticket to verify later (summaries,
    voided documents, packs, guias) or a fault."""

    cdr: Cdr | None = None
    ticket: str | None = None
    fault: Fault | None = None
    send_target: Target
    verify_ticket_target: Target | None = None
    """Where the ticket is verified."""


class VerifyResult(_Model):
    """The answer to a ticket: a CDR, no CDR yet (e.g. in progress) or a fault."""

    cdr: Cdr | None = None
    no_cdr: NoCdr | None = None
    fault: Fault | None = None


class ConsultStatus(_Model):
    """e.g. "0001" (accepted) for get_status, or "0" for validate_cdp."""

    status_code: str
    status_message: str | None = None
    cdr_zip: Bytes | None = None
    """The CDR of get_status_cdr."""


class ConsultResult(_Model):
    """The answer of the consult and validation services."""

    status: ConsultStatus | None = None
    fault: Fault | None = None
