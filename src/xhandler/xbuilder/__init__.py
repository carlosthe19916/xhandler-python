"""Creates the UBL XML of SUNAT documents: invoices (boletas and facturas),
credit and debit notes, guias de remision, perceptions, retentions, summaries,
voided documents and reversions.

Only the essential data is required: the xhandler core fills the defaults
(currency, tax rates, document types...) and computes taxes and totals before
rendering the XML.
"""

from __future__ import annotations

from typing import Any, TypeVar, cast

from xhandler._core import invoke
from xhandler.xbuilder.models import *  # noqa: F403 (the models are the API)
from xhandler.xbuilder.models import Defaults, Document
from xhandler.xbuilder.models import __all__ as __all__

D = TypeVar("D", bound=Document)


def _input(document: Document, defaults: Defaults | None) -> dict[str, Any]:
    return {
        "document": {
            "kind": document.kind,
            "spec": document.model_dump(mode="json", exclude_none=True),
        },
        "defaults": (defaults or Defaults()).model_dump(mode="json", exclude_none=True),
    }


def build(document: Document, defaults: Defaults | None = None) -> str:
    """Enriches the document and renders its XML. Without ``defaults``, or for
    the fields they leave unset, the core uses today's date in Peru and the
    current SUNAT tax rates. The document itself is not modified: use
    :func:`enrich` to get the computed values."""
    xml: str = invoke("build", _input(document, defaults))
    return xml


def enrich(document: D, defaults: Defaults | None = None) -> D:
    """Returns a copy of the document with its defaults filled in and its taxes
    and totals computed, as :func:`build` renders it."""
    spec = invoke("enrich", _input(document, defaults))
    return cast(D, type(document).model_validate(spec))
