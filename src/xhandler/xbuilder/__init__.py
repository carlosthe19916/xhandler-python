"""Creates the UBL XML of SUNAT documents: invoices (boletas and facturas),
credit and debit notes, guias de remision, perceptions, retentions, summaries,
voided documents and reversions.

Only the essential data is required: the xhandler core fills the defaults
(currency, tax rates, document types...) and computes taxes and totals before
rendering the XML.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar, cast

from xhandler._core import invoke
from xhandler.xbuilder.models import *  # noqa: F403 (the models are the API)
from xhandler.xbuilder.models import DOCUMENT_KINDS, Defaults, Document

_PERU = timezone(timedelta(hours=-5))

D = TypeVar("D", bound=Document)


def today_defaults() -> Defaults:
    """Defaults for documents issued today in Peru, with the current SUNAT tax rates."""
    return Defaults(fecha_emision=datetime.now(_PERU).date())


def _input(document: Document, defaults: Defaults | None) -> dict[str, Any]:
    kind = type(document).__name__
    if kind not in DOCUMENT_KINDS:
        raise TypeError(f"not a document: {kind}")
    return {
        "document": {"kind": kind, "spec": document.model_dump(mode="json", exclude_none=True)},
        "defaults": (defaults or today_defaults()).model_dump(mode="json", exclude_none=True),
    }


def build(document: Document, defaults: Defaults | None = None) -> str:
    """Enriches the document and renders its XML; ``defaults`` are today's by
    default. The document itself is not modified: use :func:`enrich` to get
    the computed values."""
    xml: str = invoke("build", _input(document, defaults))
    return xml


def enrich(document: D, defaults: Defaults | None = None) -> D:
    """Returns a copy of the document with its defaults filled in and its taxes
    and totals computed, as :func:`build` renders it."""
    enriched = invoke("enrich", _input(document, defaults))
    return cast(D, type(document).model_validate(enriched["spec"]))
