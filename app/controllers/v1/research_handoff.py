from fastapi import Depends, Path

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.research_handoff import ResearchLaunchRequest
from app.services import research_handoff
from app.utils import utils

router = new_router(dependencies=[Depends(base.verify_token)])


@router.post("/integrations/research/launches")
def create_research_launch(body: ResearchLaunchRequest):
    return utils.get_response(200, research_handoff.store.create(body))


@router.post("/integrations/research/launches/{launch_id}/consume")
def consume_research_launch(launch_id: str = Path(..., min_length=1)):
    consumed = research_handoff.store.consume(launch_id)
    return utils.get_response(200, consumed.model_dump(mode="json"))


@router.get("/integrations/research/launches/{launch_id}")
def get_research_launch_status(launch_id: str = Path(..., min_length=1)):
    return utils.get_response(200, research_handoff.store.status(launch_id))
