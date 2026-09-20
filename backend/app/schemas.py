from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ArtifactType(str, Enum):
    """挂载产物的合法类型：模型 / 数据集 / 日志 / 图。"""

    model = "model"
    dataset = "dataset"
    log = "log"
    graph = "graph"


ARTIFACT_TYPE_LABELS = {
    ArtifactType.model: "模型",
    ArtifactType.dataset: "数据集",
    ArtifactType.log: "日志",
    ArtifactType.graph: "图",
}


class StartRunCommand(BaseModel):
    project: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    dataset_content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    code_commit_sha: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$")
    description: str | None = None
    expected_version: int = 0


class RecordMetricCommand(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    value: float
    step: int = Field(ge=0)
    expected_version: int = Field(ge=1)


class AttachArtifactCommand(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    uri: str = Field(min_length=1, max_length=1024)
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    artifact_type: ArtifactType = Field(description="产物类型：model / dataset / log / graph")
    media_type: str | None = Field(default=None, max_length=128)
    expected_version: int = Field(ge=1)

    @field_validator("artifact_type", mode="before")
    @classmethod
    def _validate_artifact_type(cls, value: Any) -> Any:
        # 页面选择框只允许枚举值；对绕过页面直接提交的其它值，在入口处给出明确原因。
        allowed = [t.value for t in ArtifactType]
        if not isinstance(value, str) or value not in allowed:
            raise ValueError(
                f"非法产物类型: {value!r}；只允许 {allowed}（模型/数据集/日志/图）"
            )
        return value


class CompleteRunCommand(BaseModel):
    result_summary: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=1)


class AbortRunCommand(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=1)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class RunOut(BaseModel):
    id: UUID
    project: str
    name: str
    status: str
    version: int
    dataset_content_sha256: str
    code_commit_sha: str
    description: str | None
    started_at: datetime
    finished_at: datetime | None
    started_by: str
    metrics_json: list[Any]
    artifacts_json: list[Any]
    result_summary: str | None
    abort_reason: str | None

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: UUID
    aggregate_id: UUID
    version: int
    event_type: str
    payload_json: dict[str, Any]
    occurred_at: datetime
    actor: str

    model_config = {"from_attributes": True}


class LineageOut(BaseModel):
    run_id: UUID
    project: str
    name: str
    status: str
    code_commit_sha: str
    dataset_content_sha256: str
    artifacts: list[Any]
    metrics: list[Any]
    result_summary: str | None
    abort_reason: str | None
    started_at: datetime
    finished_at: datetime | None
    started_by: str
    version: int
