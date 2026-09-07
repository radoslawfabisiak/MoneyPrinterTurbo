import ast
from pathlib import Path


WEBUI = Path(__file__).parents[1] / "webui" / "research_handoff.py"


def test_webui_removes_launch_query_parameter_after_hydration():
    tree = ast.parse(WEBUI.read_text(encoding="utf-8"))
    hydrate = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "hydrate_research_launch")
    assert any(isinstance(node, ast.Delete) for node in ast.walk(hydrate))


def test_webui_handoff_does_not_log_payload_or_token():
    source = WEBUI.read_text(encoding="utf-8")
    assert "logger" not in source
    assert "print(" not in source
