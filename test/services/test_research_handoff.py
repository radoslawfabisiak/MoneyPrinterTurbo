import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from app.models.research_handoff import (
    ResearchDisplayContext,
    ResearchLaunchRequest,
    ResearchSource,
    ResearchVideoParams,
)
from app.models.exception import HttpException
from app.services.research_handoff import (
    PAYLOAD_SUFFIX,
    STATUS_SUFFIX,
    ResearchHandoffStore,
    _key,
)


class _Pipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    def set(self, key, value, ex=None):
        self.commands.append((key, value))
        return self

    def execute(self):
        with self.redis.lock:
            for key, value in self.commands:
                self.redis.data[key] = value


class _AtomicFakeRedis:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()

    def pipeline(self, transaction=True):
        return _Pipeline(self)

    def get(self, key):
        with self.lock:
            return self.data.get(key)

    def exists(self, key):
        return int(self.get(key) is not None)

    def set(self, key, value, ex=None):
        with self.lock:
            self.data[key] = value

    def eval(self, _script, _numkeys, status_key, payload_key, _status_ttl):
        with self.lock:
            status = self.data.get(status_key)
            if not status:
                return [0, ""]
            status_data = json.loads(status)
            if status_data["state"] == "CONSUMED":
                return [2, ""]
            if status_data["state"] == "EXPIRED":
                return [3, ""]
            payload = self.data.get(payload_key)
            if not payload:
                status_data["state"] = "EXPIRED"
                self.data[status_key] = json.dumps(status_data)
                return [3, ""]
            status_data["state"] = "CONSUMED"
            self.data[status_key] = json.dumps(status_data)
            del self.data[payload_key]
            return [1, payload]


def _request():
    return ResearchLaunchRequest(
        source=ResearchSource(
            workspace_id="workspace-1",
            project_id="project-1",
            research_job_id="job-1",
            brief_artifact_id="brief-1",
            brief_version=1,
            scenario_artifact_id="scenario-1",
            scenario_version=1,
            preset_id="preset-1",
            preset_version=1,
        ),
        params=ResearchVideoParams(
            video_subject="A short subject",
            video_script="A complete production script.",
            video_aspect="9:16",
            video_count=1,
            bgm_type="",
            bgm_file="",
            bgm_volume=0,
        ),
        display_context=ResearchDisplayContext(
            brief_title="Brief",
            scenario_title="Scenario",
            preset_name="Preset",
        ),
    )


def test_consume_is_single_use_and_erases_payload():
    fake = _AtomicFakeRedis()
    store = ResearchHandoffStore(fake)
    created = store.create(_request())

    consumed = store.consume(created["launch_id"])

    assert consumed.task_id == created["task_id"]
    assert fake.get(_key(created["launch_id"], PAYLOAD_SUFFIX)) is None
    assert store.status(created["launch_id"])["state"] == "CONSUMED"
    with pytest.raises(HttpException) as error:
        store.consume(created["launch_id"])
    assert error.value.status_code == 409


def test_concurrent_consumers_have_one_winner():
    fake = _AtomicFakeRedis()
    store = ResearchHandoffStore(fake)
    launch_id = store.create(_request())["launch_id"]

    def consume():
        try:
            store.consume(launch_id)
            return "ok"
        except HttpException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: consume(), range(2)))
    assert sorted(results, key=str) == [409, "ok"]


@pytest.mark.parametrize(
    ("field", "value"),
    (("video_script", "   "), ("video_aspect", "16:9"), ("video_count", 2), ("bgm_type", "random")),
)
def test_research_params_reject_generation_that_breaks_contract(field, value):
    values = _request().params.model_dump()
    values[field] = value
    with pytest.raises(ValueError):
        ResearchVideoParams.model_validate(values)


def test_research_params_reject_unknown_fields():
    values = _request().params.model_dump()
    values["cross_post"] = True
    with pytest.raises(ValueError):
        ResearchVideoParams.model_validate(values)
