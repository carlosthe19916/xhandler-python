"""Reads the corpus that every xhandler binding must pass (testdata/conformance,
synced from xhandler-rust)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CORPUS = Path(__file__).parent.parent / "testdata" / "conformance"


@dataclass
class Case:
    op: str
    name: str
    input: Any
    expected: dict[str, Any]

    @property
    def id(self) -> str:
        return f"{self.op}/{self.name}"


def cases(op: str | None = None) -> list[Case]:
    found = []
    for path in sorted(CORPUS.rglob("*.json")):
        case_op, *name = path.relative_to(CORPUS).with_suffix("").parts
        if op is None or case_op == op:
            data = json.loads(path.read_bytes())
            found.append(Case(case_op, "/".join(name), data["input"], data["expected"]))
    if not found:
        raise RuntimeError(f"no conformance cases in {CORPUS} (run make sync)")
    return found
