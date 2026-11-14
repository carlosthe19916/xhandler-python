import base64
from decimal import Decimal

import pytest
from conformance import Case, cases

from xhandler import XhandlerError, xbuilder
from xhandler.xsigner import SigningKey, sign


def signing_key(key: dict) -> SigningKey:
    if "pem" in key:
        return SigningKey.from_pem(key["pem"]["private_key"], key["pem"]["certificate"])
    return SigningKey.from_pkcs12(base64.b64decode(key["pkcs12"]["der"]), key["pkcs12"]["password"])


@pytest.mark.parametrize(
    "case",
    # xml_not_base64 can't be expressed with bytes
    [c for c in cases("sign") if c.name != "errors/xml_not_base64"],
    ids=lambda c: c.name,
)
def test_sign_corpus(case: Case) -> None:
    xml = base64.b64decode(case.input["xml"])
    key = signing_key(case.input["key"])

    if "error" in case.expected:
        with pytest.raises(XhandlerError) as error:
            sign(xml, key)
        assert error.value.kind.value == case.expected["error"]["kind"]
    else:
        assert sign(xml, key) == base64.b64decode(case.expected["ok"])


def test_signs_built_documents() -> None:
    invoice = xbuilder.Invoice(
        serie_numero="F001-1",
        proveedor=xbuilder.Proveedor(ruc="12345678912", razon_social="Softgreen S.A.C."),
        cliente=xbuilder.Cliente(
            tipo_documento_identidad="6",
            numero_documento_identidad="12121212121",
            nombre="Carlos Feria",
        ),
        detalles=[xbuilder.Detalle(descripcion="Item", cantidad=Decimal(1), precio=Decimal(100))],
    )
    llama = next(c for c in cases("sign") if c.name == "pkcs12/llama")
    signed = sign(xbuilder.build(invoice), signing_key(llama.input["key"]))
    assert 'xmldsig#" Id="PROJECT-OPENUBL-SIGN">' in signed


def test_signing_key_hides_its_secrets() -> None:
    pem = next(c for c in cases("sign") if c.name == "pem/min_data_ruc")
    assert "PRIVATE KEY" not in repr(signing_key(pem.input["key"]))
