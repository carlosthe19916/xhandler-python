"""Runs the operations of the xhandler WebAssembly module.

The module exports one JSON entry point (see xhandler-rust/xhandler-wasm): the
request is ``{"op", "input"}`` and the response ``{"ok": ...}`` or
``{"error": {"kind", "message"}}``.
"""

from __future__ import annotations

import contextlib
import json
import os
import queue
import threading
from enum import Enum
from importlib import resources
from typing import Any

import wasmtime

CORE_VERSION = resources.files(__package__).joinpath("VERSION").read_text(encoding="utf-8").strip()
"""Version of the embedded xhandler core."""


class ErrorKind(str, Enum):
    """Classifies the errors reported by the xhandler core."""

    INVALID_REQUEST = "invalid_request"
    """The request did not reach an operation."""
    INVALID_INPUT = "invalid_input"
    """The input has missing fields or wrong types."""
    VALIDATION = "validation"
    """The document has invalid values, e.g. an unknown catalog code."""
    RENDER = "render"
    """The XML could not be rendered."""
    INVALID_KEY = "invalid_key"
    """The private key or certificate can't be read (e.g. a wrong keystore
    password), or the certificate is not the one of the private key."""
    RESPONSE = "response"
    """The answer of SUNAT can't be read, e.g. an HTML error page."""
    RATE_LIMITED = "rate_limited"
    """SUNAT's front proxy refused the request; the SunatClient already retried it."""


class XhandlerError(Exception):
    """An error reported by the xhandler core."""

    def __init__(self, kind: ErrorKind, message: str) -> None:
        super().__init__(f"xhandler {kind.value}: {message}")
        self.kind = kind
        self.message = message


def invoke(op: str, input: Any = None) -> Any:
    """Runs ``op`` with ``input`` (JSON-serializable) and returns its result."""
    response = json.loads(invoke_raw(json.dumps({"op": op, "input": input}).encode()))
    if "error" in response:
        error = response["error"]
        raise XhandlerError(ErrorKind(error["kind"]), error["message"])
    return response["ok"]


def invoke_raw(request: bytes) -> bytes:
    """Sends a JSON request to the module and returns its JSON response."""
    instance = _pool.get()
    # On a trap (e.g. a panic in the core) the instance is unusable: it raises
    # and is not returned to the pool.
    response = instance.invoke(request)
    _pool.put(instance)
    return response


class _Instance:
    """A module instance: runs one call at a time."""

    def __init__(self, engine: wasmtime.Engine, module: wasmtime.Module) -> None:
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        self._store = wasmtime.Store(engine)
        self._store.set_wasi(wasmtime.WasiConfig())
        exports = linker.instantiate(self._store, module).exports(self._store)
        exports["_initialize"](self._store)  # type: ignore[operator]
        self._memory: wasmtime.Memory = exports["memory"]  # type: ignore[assignment]
        self._alloc: wasmtime.Func = exports["xh_alloc"]  # type: ignore[assignment]
        self._free: wasmtime.Func = exports["xh_free"]  # type: ignore[assignment]
        self._call: wasmtime.Func = exports["xh_invoke"]  # type: ignore[assignment]

    def invoke(self, request: bytes) -> bytes:
        """Runs one request. After a trap the instance must be discarded, so
        nothing is freed then."""
        store = self._store
        ptr = self._alloc(store, len(request))
        self._memory.write(store, request, ptr)
        # wasmtime returns i64 results as signed integers
        packed = self._call(store, ptr, len(request)) & 0xFFFFFFFFFFFFFFFF
        response_ptr, response_len = packed >> 32, packed & 0xFFFFFFFF
        response = bytes(self._memory.read(store, response_ptr, response_ptr + response_len))
        self._free(store, ptr, len(request))
        self._free(store, response_ptr, response_len)
        return response


class _Pool:
    """Idle module instances: an instance parses the XML templates on its first
    use, so it is worth reusing. The module is compiled once, on first use."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._module: tuple[wasmtime.Engine, wasmtime.Module] | None = None
        self._idle: queue.Queue[_Instance] = queue.Queue(maxsize=os.cpu_count() or 4)

    def get(self) -> _Instance:
        try:
            return self._idle.get_nowait()
        except queue.Empty:
            return _Instance(*self._compiled())

    def put(self, instance: _Instance) -> None:
        # When the pool is full the instance is dropped for the garbage collector.
        with contextlib.suppress(queue.Full):
            self._idle.put_nowait(instance)

    def _compiled(self) -> tuple[wasmtime.Engine, wasmtime.Module]:
        with self._lock:
            if self._module is None:
                engine = wasmtime.Engine()
                wasm = resources.files(__package__).joinpath("xhandler.wasm").read_bytes()
                self._module = (engine, wasmtime.Module(engine, wasm))
            return self._module


_pool = _Pool()
