"""Creates, signs and sends an invoice to SUNAT beta. It needs the network, so
it only runs with XHANDLER_E2E=true."""

import os
import time
from decimal import Decimal

import pytest
from conformance import cases

from xhandler import xbuilder
from xhandler.xsender import Credentials, FileSender, Status, URLs
from xhandler.xsigner import KeyPair, sign

pytestmark = pytest.mark.skipif(
    os.environ.get("XHANDLER_E2E") != "true", reason="set XHANDLER_E2E=true to send to SUNAT beta"
)


def _key_pair() -> KeyPair:
    """The test certificate of the corpus, the one SUNAT beta accepts for RUC 12345678912."""
    pem = next(c for c in cases("sign") if c.name == "pem/min_data_ruc").input["key"]["pem"]
    return KeyPair.from_pem(pem["private_key"], pem["certificate"])


def test_create_sign_and_send_to_sunat_beta() -> None:
    invoice = xbuilder.Invoice(
        # A new number each run: SUNAT beta remembers the documents
        serie_numero=f"F001-{int(time.time()) % 100_000_000}",
        proveedor=xbuilder.Proveedor(ruc="12345678912", razon_social="Softgreen S.A.C."),
        cliente=xbuilder.Cliente(
            tipo_documento_identidad="6",
            numero_documento_identidad="12121212121",
            nombre="Carlos Feria",
        ),
        detalles=[xbuilder.Detalle(descripcion="Item", cantidad=Decimal(2), precio=Decimal(100))],
    )
    signed = sign(xbuilder.build(invoice).encode(), _key_pair())

    sender = FileSender(
        URLs.beta(), Credentials(username="12345678959MODDATOS", password="MODDATOS")
    )
    result = sender.send_file(signed)

    assert result.cdr is not None, result.fault
    assert result.cdr.response_code == "0"
    assert result.cdr.status is Status.ACCEPTED
