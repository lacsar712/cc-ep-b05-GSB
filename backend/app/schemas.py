from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.cqrs import ARTIFACT_TYPE_LABELS, ArtifactType


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
    artifact_type: ArtifactType = Field(
        ..., description="产物类型:model(模型)/dataset(数据集)/log(日志)/graph(图)"
    )
    uri: str = Field(min_length=1, max_length=1024)
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
    media_type: str | None = Field(default=None, max_length=128)
    expected_version: int = Field(ge=1)

    @field_validator("artifact_type", mode="before")
    @classmethod
    def _validate_artifact_type(cls, v: Any) -> ArtifactType:
        # 入口层先拦一次：非法值给出明确中文原因
        try:
            return ArtifactType(v)
        except (ValueError, TypeError):
            allowed = "、".join(
                f"{t.value}（{ARTIFACT_TYPE_LABELS[t.value]}）" for t in ArtifactType
            )
            raise ValueError(
                f"产物类型非法：{v!r} 不在允许范围内，仅支持 {allowed}"
            ) from None


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
