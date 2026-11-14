import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from conformance import Case, cases

import xhandler
from xhandler import _core


@pytest.mark.parametrize("case", cases(), ids=lambda c: c.id)
def test_conformance(case: Case) -> None:
    request = json.dumps({"op": case.op, "input": case.input}).encode()
    response = json.loads(_core.invoke_raw(request))

    if "error" in case.expected:
        assert response.get("error", {}).get("kind") == case.expected["error"]["kind"], response
    else:
        assert response == case.expected


def test_version_matches_synced_core() -> None:
    synced = (Path(_core.__file__).parent / "VERSION").read_text(encoding="utf-8").strip()
    assert _core.invoke("version") == synced == xhandler.CORE_VERSION


def test_errors_are_typed() -> None:
    with pytest.raises(xhandler.XhandlerError) as error:
        _core.invoke("nope")
    assert error.value.kind is xhandler.ErrorKind.INVALID_REQUEST


def test_concurrent_calls() -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        versions = set(pool.map(lambda _: _core.invoke("version"), range(32)))
    assert versions == {xhandler.CORE_VERSION}
