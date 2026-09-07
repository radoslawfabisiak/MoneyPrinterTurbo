from fastapi import Depends

from app.controllers import base
from app.controllers.v1 import research_handoff


def test_research_routes_are_protected_by_api_key_dependency():
    assert any(
        dependency.dependency is base.verify_token
        for dependency in research_handoff.router.dependencies
    )


def test_research_routes_are_registered_under_expected_paths():
    paths = {route.path for route in research_handoff.router.routes}
    assert "/api/v1/integrations/research/launches" in paths
    assert "/api/v1/integrations/research/launches/{launch_id}" in paths
    assert "/api/v1/integrations/research/launches/{launch_id}/consume" in paths
