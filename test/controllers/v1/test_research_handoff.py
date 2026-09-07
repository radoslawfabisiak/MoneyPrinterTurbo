import pytest

from app.models.exception import HttpException
from app.models.research_handoff import ResearchLaunchRequest
from app.services.research_handoff import ResearchHandoffStore

from test.services.test_research_handoff import _AtomicFakeRedis, _request


def test_handoff_request_rejects_unknown_fields():
    value = _request().model_dump()
    value["unexpected"] = "rejected"
    with pytest.raises(ValueError):
        ResearchLaunchRequest.model_validate(value)


def test_handoff_consume_keeps_status_but_deletes_payload():
    redis = _AtomicFakeRedis()
    store = ResearchHandoffStore(redis)
    created = store.create(_request())
    store.consume(created["launch_id"])
    assert store.status(created["launch_id"])["state"] == "CONSUMED"
    with pytest.raises(HttpException) as error:
        store.consume(created["launch_id"])
    assert error.value.status_code == 409
