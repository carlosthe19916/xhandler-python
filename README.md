# xhandler-python

Create, sign and send the electronic documents (UBL XML) of SUNAT Peru from Python.

- **xhandler.xbuilder**: invoices (boletas and facturas), credit and debit notes, guías
  de remisión, perceptions, retentions, summaries, voided documents and reversions. Only
  the essential data is required: defaults, taxes and totals are computed.
- **xhandler.xsigner**: the enveloped RSA-SHA256 XML signature SUNAT requires (PEM or
  PKCS#12).
- **xhandler.xsender**: SUNAT's SOAP services (billService, consult and validation) and
  the REST API of the guías de remisión, with the CDR, tickets and faults already read.

No native extension to compile: the work is done by the
[xhandler](https://github.com/project-openubl/xhandler-rust) Rust core, embedded as a
WebAssembly module and run with [wasmtime](https://github.com/bytecodealliance/wasmtime-py).
The Go and Java libraries use the same core, so the three produce the same XML,
signatures and requests.

## Install

```shell
pip install xhandler
```

Python 3.10 or newer.

## Usage

```python
from decimal import Decimal
from pathlib import Path

from xhandler import xbuilder
from xhandler.xsender import Credentials, FileSender, URLs
from xhandler.xsigner import SigningKey, sign

# Create
invoice = xbuilder.Invoice(
    serie_numero="F001-1",
    proveedor=xbuilder.Proveedor(ruc="12345678912", razon_social="Softgreen S.A.C."),
    cliente=xbuilder.Cliente(
        tipo_documento_identidad="6",  # RUC (Catalog6)
        numero_documento_identidad="12121212121",
        nombre="Carlos Feria",
    ),
    detalles=[xbuilder.Detalle(descripcion="Item", cantidad=Decimal(2), precio=Decimal("100.00"))],
)
xml = xbuilder.build(invoice)  # today in Peru, current tax rates

# Sign
key = SigningKey.from_pkcs12(Path("certificate.pfx").read_bytes(), "password")
signed = sign(xml.encode(), key)

# Send
sender = FileSender(URLs.beta(), Credentials(username="12345678959MODDATOS", password="MODDATOS"))
result = sender.send_file(signed)
if result.cdr:
    # ACEPTADO La Factura numero F001-1, ha sido aceptada
    print(result.cdr.status, result.cdr.description)
elif result.ticket:  # summaries, voided documents, guías
    verified = sender.verify_file_ticket(signed, result.ticket)
else:
    print(result.fault.status, result.fault.message)
```

- `xbuilder.enrich` returns the document with the computed values (taxes, totals,
  legends) instead of the XML. `xbuilder.Defaults` overrides the date or the tax rates.
- Errors of the core are `xhandler.XhandlerError` with a `kind`: `ErrorKind.VALIDATION`
  (e.g. an unknown catalog code), `ErrorKind.INVALID_KEY`, `ErrorKind.RESPONSE`...
- Guías de remisión need `URLs.production()` (SUNAT has no beta for them) and the
  `client_id`/`client_secret` of the API client. Share one `SunatClient` between the
  `FileSender`s of several companies: it keeps the connections and the tokens.

## Development

The WebAssembly module, the models (`src/xhandler/xbuilder/models.py`) and the
conformance corpus (`testdata/conformance`) come from xhandler-rust:

```shell
make sync RUST_REPO=../xhandler-rust   # runs make -C xhandler-wasm dist there and copies the results
make test                               # every corpus case, raw and through the models
make lint
XHANDLER_E2E=true uv run pytest tests/test_e2e.py   # creates, signs and sends an invoice to SUNAT beta
```

## License

[Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0)
