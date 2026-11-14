"""Signs UBL documents with the enveloped RSA-SHA256 XML signature SUNAT
requires. The signature is placed in the first empty ``ext:ExtensionContent``
of the document, as rendered by :mod:`xhandler.xbuilder`."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from xhandler._core import invoke


@dataclass(frozen=True)
class KeyPair:
    """The private key and certificate that sign the documents. The key is
    checked when signing."""

    _key: dict[str, Any]

    @classmethod
    def from_pem(cls, private_key: str, certificate: str) -> KeyPair:
        """A PEM private key (PKCS#8 or PKCS#1) and a PEM X.509 certificate."""
        return cls({"pem": {"private_key": private_key, "certificate": certificate}})

    @classmethod
    def from_pkcs12(cls, der: bytes, password: str) -> KeyPair:
        """The key pair stored in a PKCS#12 keystore (.pfx, .p12)."""
        return cls({"pkcs12": {"der": base64.b64encode(der).decode(), "password": password}})


def sign(xml: bytes | str, key: KeyPair) -> bytes:
    """Returns the XML with its signature. The XML may be UTF-8 or ISO-8859-1
    bytes, or text; the signed XML is UTF-8."""
    data = xml.encode() if isinstance(xml, str) else xml
    signed: str = invoke("sign", {"xml": base64.b64encode(data).decode(), "key": key._key})
    return base64.b64decode(signed)
