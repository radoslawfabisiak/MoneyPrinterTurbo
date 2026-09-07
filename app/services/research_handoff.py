import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import redis

from app.config import config
from app.models.exception import HttpException
from app.models.research_handoff import (
    ResearchConsumedLaunch,
    ResearchDisplayContext,
    ResearchLaunchRequest,
    ResearchSource,
    ResearchVideoParams,
)

PAYLOAD_PREFIX = "research:launch:"
STATUS_SUFFIX = ":status"
PAYLOAD_SUFFIX = ":payload"
STATUS_TTL_SECONDS = 24 * 60 * 60

_CONSUME_SCRIPT = """
local status = redis.call('GET', KEYS[1])
if not status then return {0, ''} end
if string.find(status, '"state":"CONSUMED"', 1, true) then return {2, ''} end
if string.find(status, '"state":"EXPIRED"', 1, true) then return {3, ''} end
local payload = redis.call('GET', KEYS[2])
if not payload then
  status = string.gsub(status, '"state":"CREATED"', '"state":"EXPIRED"', 1)
  redis.call('SET', KEYS[1], status, 'EX', ARGV[1])
  return {3, ''}
end
status = string.gsub(status, '"state":"CREATED"', '"state":"CONSUMED"', 1)
redis.call('SET', KEYS[1], status, 'EX', ARGV[1])
redis.call('DEL', KEYS[2])
return {1, payload}
"""


def _key(launch_id: str, suffix: str) -> str:
    return f"{PAYLOAD_PREFIX}{launch_id}{suffix}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_zulu(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _redis_client():
    return redis.StrictRedis(
        host=config.app.get("redis_host", "localhost"),
        port=int(config.app.get("redis_port", 6379)),
        db=int(config.app.get("redis_db", 0)),
        password=config.app.get("redis_password") or None,
        decode_responses=True,
    )


class ResearchHandoffStore:
    def __init__(self, client=None):
        self.redis = client or _redis_client()

    def create(self, request: ResearchLaunchRequest) -> dict:
        launch_id = str(uuid4())
        task_id = str(uuid4())
        expires_at = _utc_now() + timedelta(seconds=request.expires_in_seconds)
        payload = {
            "source": request.source.model_dump(mode="json"),
            "params": request.params.model_dump(mode="json"),
            "display_context": request.display_context.model_dump(mode="json"),
            "task_id": task_id,
            "expires_at": _as_zulu(expires_at),
        }
        status = {
            "launch_id": launch_id,
            "task_id": task_id,
            "state": "CREATED",
            "expires_at": _as_zulu(expires_at),
        }
        payload_key = _key(launch_id, PAYLOAD_SUFFIX)
        status_key = _key(launch_id, STATUS_SUFFIX)
        pipe = self.redis.pipeline(transaction=True)
        pipe.set(
            payload_key,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            ex=request.expires_in_seconds,
        )
        pipe.set(
            status_key,
            json.dumps(status, ensure_ascii=False, separators=(",", ":")),
            ex=STATUS_TTL_SECONDS,
        )
        pipe.execute()
        return {
            "launch_id": launch_id,
            "task_id": task_id,
            "expires_at": expires_at,
            "webui_path": f"/?research_launch={launch_id}",
        }

    def consume(self, launch_id: str) -> ResearchConsumedLaunch:
        launch_id = _validate_uuid(launch_id)
        result = self.redis.eval(
            _CONSUME_SCRIPT,
            2,
            _key(launch_id, STATUS_SUFFIX),
            _key(launch_id, PAYLOAD_SUFFIX),
            STATUS_TTL_SECONDS,
        )
        code = int(result[0])
        if code == 0:
            raise HttpException(launch_id, 404, "research launch not found")
        if code == 2:
            raise HttpException(launch_id, 409, "research launch already consumed")
        if code == 3:
            raise HttpException(launch_id, 410, "research launch expired")
        return ResearchConsumedLaunch.model_validate(json.loads(result[1]))

    def status(self, launch_id: str) -> dict:
        launch_id = _validate_uuid(launch_id)
        key = _key(launch_id, STATUS_SUFFIX)
        raw = self.redis.get(key)
        if not raw:
            raise HttpException(launch_id, 404, "research launch not found")
        value = json.loads(raw)
        if value.get("state") == "CREATED" and not self.redis.exists(
            _key(launch_id, PAYLOAD_SUFFIX)
        ):
            value["state"] = "EXPIRED"
            self.redis.set(
                key,
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                ex=STATUS_TTL_SECONDS,
            )
        return {
            "launch_id": launch_id,
            "task_id": value["task_id"],
            "state": value["state"],
            "expires_at": value["expires_at"],
        }


def _validate_uuid(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HttpException(str(value), 404, "research launch not found") from exc


store = ResearchHandoffStore()
