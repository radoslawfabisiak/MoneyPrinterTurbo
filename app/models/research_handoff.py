from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.schema import VideoParams


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=1, max_length=200)
    research_job_id: str = Field(min_length=1, max_length=200)
    brief_artifact_id: str = Field(min_length=1, max_length=200)
    brief_version: int = Field(ge=1)
    scenario_artifact_id: str = Field(min_length=1, max_length=200)
    scenario_version: int = Field(ge=1)
    preset_id: str = Field(min_length=1, max_length=200)
    preset_version: int = Field(ge=1)


class ResearchVideoParams(VideoParams):
    """The restricted parameter set accepted by a Research handoff."""

    model_config = ConfigDict(extra="forbid")
    video_fit_mode: Literal["cover"] = "cover"

    @model_validator(mode="after")
    def validate_research_defaults(self):
        if not self.video_script.strip():
            raise ValueError("video_script must be non-empty")
        if self.video_aspect != "9:16":
            raise ValueError("video_aspect must be 9:16")
        if self.video_count != 1:
            raise ValueError("video_count must be 1")
        if (self.bgm_type or "").strip() or (self.bgm_file or "").strip():
            raise ValueError("background music must be disabled")
        if self.bgm_volume not in (None, 0, 0.0):
            raise ValueError("bgm_volume must be 0")
        return self


class ResearchDisplayContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief_title: str = Field(min_length=1, max_length=500)
    scenario_title: str = Field(min_length=1, max_length=500)
    preset_name: str = Field(min_length=1, max_length=500)


class ResearchLaunchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: ResearchSource
    params: ResearchVideoParams
    display_context: ResearchDisplayContext
    expires_in_seconds: int = Field(default=900, ge=60, le=3600)


class ResearchLaunchResponse(BaseModel):
    launch_id: str
    task_id: str
    expires_at: datetime
    webui_path: str


class ResearchConsumedLaunch(BaseModel):
    source: ResearchSource
    params: ResearchVideoParams
    display_context: ResearchDisplayContext
    task_id: str
    expires_at: datetime
