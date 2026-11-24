"""Safety rule: Trader modules T1-T5 (the order path) must never import the LLM client."""

import ast
from pathlib import Path

import pytest

TRADER = Path(__file__).resolve().parents[1] / "openrange" / "agents" / "trader"
ORDER_PATH = ["t1_signals.py", "t2_gate.py", "t3_risk.py", "t4_broker.py", "t5_monitor.py"]
FORBIDDEN = ("openrange.core.llm", "google.genai", "anthropic")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("filename", ORDER_PATH)
def test_order_path_module_does_not_import_llm(filename):
    imports = imported_modules(TRADER / filename)
    bad = [m for m in imports if m.startswith(FORBIDDEN)]
    assert not bad, f"{filename} imports {bad}: the LLM must not be in the order path"
