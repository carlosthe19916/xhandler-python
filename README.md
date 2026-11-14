# xhandler-python

[![License](https://img.shields.io/github/license/project-openubl/xhandler-python?logo=apache)](https://www.apache.org/licenses/LICENSE-2.0)
[![CI](https://github.com/project-openubl/xhandler-python/actions/workflows/ci.yml/badge.svg)](https://github.com/project-openubl/xhandler-python/actions/workflows/ci.yml)

Crea, firma y envía los comprobantes electrónicos (XML UBL) de la SUNAT del Perú desde Python.

| Módulo | Qué hace |
|---|---|
| `xhandler.xbuilder` | Crea el XML de facturas, boletas, notas de crédito y débito, guías de remisión, percepciones, retenciones, resúmenes diarios, comunicaciones de baja y reversiones. Solo das los datos esenciales: los valores por defecto, impuestos y totales se calculan |
| `xhandler.xsigner` | Firma el XML (RSA-SHA256, certificados PEM o PKCS#12) |
| `xhandler.xsender` | Envía a la SUNAT (servicios SOAP y API REST de guías) y lee el CDR, tickets y errores |

Sin extensiones nativas que compilar: el trabajo lo hace el
[núcleo xhandler](https://github.com/project-openubl/xhandler-rust), incrustado como un módulo
WebAssembly. Las librerías de Go y Java usan el mismo núcleo, así que las tres producen el mismo
XML, las mismas firmas y las mismas peticiones. Los modelos están tipados
([pydantic](https://docs.pydantic.dev)).

## Instalación

Hasta la primera versión en PyPI, instálalo desde GitHub:

```shell
pip install "xhandler @ git+https://github.com/project-openubl/xhandler-python"
# o
uv add "xhandler @ git+https://github.com/project-openubl/xhandler-python"
```

Python 3.10 o superior, en Linux, macOS y Windows.

## Uso

```python
from decimal import Decimal
from pathlib import Path

from xhandler import xbuilder
from xhandler.xsender import Credentials, FileSender, URLs
from xhandler.xsigner import SigningKey, sign

# Crear
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
xml = xbuilder.build(invoice)  # fecha de hoy en Perú y tasas vigentes

# Firmar
key = SigningKey.from_pkcs12(Path("certificado.pfx").read_bytes(), "password")
signed = sign(xml.encode(), key)

# Enviar
sender = FileSender(URLs.beta(), Credentials(username="12345678959MODDATOS", password="MODDATOS"))
result = sender.send_file(signed)
if result.cdr:
    # ACEPTADO La Factura numero F001-1, ha sido aceptada
    print(result.cdr.status, result.cdr.description)
elif result.ticket:  # resúmenes, bajas y guías: consulta el ticket después
    print(sender.verify_file_ticket(signed, result.ticket))
else:
    print(result.fault.status, result.fault.code, result.fault.message)
```

- **Crear**: `xbuilder.enrich` devuelve el documento con los valores calculados (impuestos,
  totales, leyendas) en lugar del XML. `xbuilder.Defaults` cambia la fecha de emisión o las tasas.
- **Firmar**: `SigningKey.from_pem(llave_privada, certificado)` para archivos PEM. `sign` devuelve
  texto si recibe texto y bytes si recibe bytes.
- **Enviar**: `send_pack` envía varias facturas en un zip. `SunatClient` también tiene los
  servicios de consulta y validación (`get_status`, `get_status_cdr`, `validate_cdp`,
  `validate_file`). Si envías por varias empresas, comparte un `SunatClient` (conexiones y tokens)
  entre sus `FileSender`.
- **Guías de remisión**: usan `URLs.production()` (la SUNAT no tiene beta para ellas) y el
  `client_id`/`client_secret` de la API.
- **Errores**: los del núcleo lanzan `xhandler.XhandlerError` con un `kind`: `ErrorKind.VALIDATION`
  (p. ej. un código de catálogo inválido), `ErrorKind.INVALID_KEY`, `ErrorKind.RESPONSE`... Los
  rechazos de la SUNAT no son errores: llegan en `result.fault`.

## Contribuir

Revisa [CONTRIBUTING.md](CONTRIBUTING.md). Preguntas e ideas en el
[chat de Zulip](https://projectopenubl.zulipchat.com/).

## Licencia

[Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0)
