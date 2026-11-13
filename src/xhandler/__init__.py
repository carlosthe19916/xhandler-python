"""Create, sign and send the electronic documents (UBL XML) of SUNAT Peru.

The work is done by the xhandler Rust core, embedded as a WebAssembly module:
see the ``xhandler.xbuilder``, ``xhandler.xsigner`` and ``xhandler.xsender``
packages.
"""

from xhandler._core import CORE_VERSION, ErrorKind, XhandlerError

__all__ = ["CORE_VERSION", "ErrorKind", "XhandlerError"]
