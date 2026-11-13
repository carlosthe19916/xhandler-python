from datetime import date
from decimal import Decimal

import pytest
from conformance import Case, cases

from xhandler import ErrorKind, XhandlerError, xbuilder


def document_of(tagged: dict) -> xbuilder.Document:
    """Decodes a corpus document into its model; unknown fields fail, so a model
    change in Rust that was not synced breaks the tests."""
    model = getattr(xbuilder, tagged["kind"])
    return model.model_validate(tagged["spec"])


def defaults_of(case: Case) -> xbuilder.Defaults:
    return xbuilder.Defaults.model_validate(case.input["defaults"])


@pytest.mark.parametrize(
    "case", [c for c in cases("build") if "ok" in c.expected], ids=lambda c: c.name
)
def test_build_corpus_through_models(case: Case) -> None:
    document = document_of(case.input["document"])
    assert xbuilder.build(document, defaults_of(case)) == case.expected["ok"]


@pytest.mark.parametrize("case", cases("enrich"), ids=lambda c: c.name)
def test_enrich_corpus_through_models(case: Case) -> None:
    document = document_of(case.input["document"])
    expected = document_of(case.expected["ok"])
    assert xbuilder.enrich(document, defaults_of(case)) == expected


def invoice() -> xbuilder.Invoice:
    return xbuilder.Invoice(
        serie_numero="F001-1",
        proveedor=xbuilder.Proveedor(ruc="12345678912", razon_social="Softgreen S.A.C."),
        cliente=xbuilder.Cliente(
            tipo_documento_identidad="6",
            numero_documento_identidad="12121212121",
            nombre="Carlos Feria",
        ),
        detalles=[xbuilder.Detalle(descripcion="Item", cantidad=Decimal(2), precio=Decimal(100))],
    )


def test_enrich_computes_totals() -> None:
    defaults = xbuilder.Defaults(fecha_emision=date(2019, 12, 24))
    enriched = xbuilder.enrich(invoice(), defaults)
    assert enriched.total_importe is not None
    assert enriched.total_importe.importe == Decimal("236")
    assert enriched.moneda == "PEN"
    assert enriched.fecha_emision == date(2019, 12, 24)


def test_build_reports_validation_errors() -> None:
    document = invoice()
    document.detalles[0].igv_tipo = "XX"
    with pytest.raises(XhandlerError) as error:
        xbuilder.build(document)
    assert error.value.kind is ErrorKind.VALIDATION


def test_build_rejects_non_documents() -> None:
    with pytest.raises(TypeError):
        xbuilder.build(xbuilder.Proveedor(ruc="1", razon_social="x"))  # type: ignore[arg-type]
