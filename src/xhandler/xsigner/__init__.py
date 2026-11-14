"""Signs UBL documents with the enveloped RSA-SHA256 XML signature SUNAT
requires. The signature is placed in the first empty ``ext:ExtensionContent``
of the document, as rendered by :mod:`xhandler.xbuilder`."""

from __future__ import annotations

import base64
from typing import Any, overload

from xhandler._core import invoke


class KeyPair:
    """The private key and certificate that sign the documents. The key is
    checked when signing. It never shows its secrets in ``repr``."""

    __slots__ = ("_key",)

    def __init__(self, key: dict[str, Any]) -> None:
        self._key = key

    @classmethod
    def from_pem(cls, private_key: str, certificate: str) -> KeyPair:
        """A PEM private key (PKCS#8 or PKCS#1) and a PEM X.509 certificate."""
        return cls({"pem": {"private_key": private_key, "certificate": certificate}})

    @classmethod
    def from_pkcs12(cls, der: bytes, password: str) -> KeyPair:
        """The key pair stored in a PKCS#12 keystore (.pfx, .p12)."""
        return cls({"pkcs12": {"der": base64.b64encode(der).decode(), "password": password}})

    def __repr__(self) -> str:
        return "KeyPair(<redacted>)"


@overload
def sign(xml: bytes, key: KeyPair) -> bytes: ...
@overload
def sign(xml: str, key: KeyPair) -> str: ...
def sign(xml: bytes | str, key: KeyPair) -> bytes | str:
    """Returns the XML with its signature, as bytes for bytes and as text for
    text. Bytes may be UTF-8 or ISO-8859-1 (as their XML declaration says);
    the signed bytes are UTF-8."""
    data = xml.encode() if isinstance(xml, str) else xml
    signed = base64.b64decode(
        invoke("sign", {"xml": base64.b64encode(data).decode(), "key": key._key})
    )
    return signed.decode() if isinstance(xml, str) else signed
