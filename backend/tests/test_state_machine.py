import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cqrs import (
    ARTIFACT_TYPE_LABELS,
    ConflictError,
    DomainError,
    abort_run,
    attach_artifact,
    complete_run,
    list_events,
    rebuild_projection_from_events,
    record_metric,
    start_run,
)
from app.database import Base
from app.models import RunProjection


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # JSONB not available on SQLite — remap via create_all with JSON
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import JSONB

    # For SQLite tests, compile JSONB as JSON
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def _compile_jsonb_sqlite(_type, compiler, **kw):
        return "JSON"

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_start_and_complete_happy_path(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds"),
        code_commit_sha="abc1234",
        description="d",
    )
    assert run.status == "running"
    assert run.version == 1

    run = record_metric(
        db,
        run_id=run.id,
        actor="researcher",
        name="acc",
        value=0.9,
        step=1,
        expected_version=1,
    )
    assert run.version == 2
    assert len(run.metrics_json) == 1

    run = complete_run(
        db,
        run_id=run.id,
        actor="researcher",
        result_summary="done",
        expected_version=2,
    )
    assert run.status == "completed"
    assert run.version == 3

    with pytest.raises(ConflictError):
        record_metric(
            db,
            run_id=run.id,
            actor="researcher",
            name="acc",
            value=0.95,
            step=2,
            expected_version=3,
        )


def test_optimistic_lock_conflict(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds2"),
        code_commit_sha="abc1234",
        description=None,
    )
    with pytest.raises(ConflictError):
        record_metric(
            db,
            run_id=run.id,
            actor="researcher",
            name="loss",
            value=1.0,
            step=1,
            expected_version=0,
        )


def test_abort_terminal(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds3"),
        code_commit_sha="abc1234",
        description=None,
    )
    run = abort_run(
        db,
        run_id=run.id,
        actor="researcher",
        reason="OOM",
        expected_version=1,
    )
    assert run.status == "aborted"
    with pytest.raises(ConflictError):
        complete_run(
            db,
            run_id=run.id,
            actor="researcher",
            result_summary="nope",
            expected_version=2,
        )


def test_projection_matches_event_replay(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds4"),
        code_commit_sha="deadbeef",
        description="x",
        run_id=uuid4(),
    )
    run = record_metric(
        db,
        run_id=run.id,
        actor="researcher",
        name="f1",
        value=1.5,
        step=0,
        expected_version=run.version,
    )
    run = attach_artifact(
        db,
        run_id=run.id,
        actor="researcher",
        name="model.bin",
        artifact_type="log",
        uri="file:///tmp/model.bin",
        content_sha256=sha("model"),
        media_type="application/octet-stream",
        expected_version=run.version,
    )
    run = complete_run(
        db,
        run_id=run.id,
        actor="researcher",
        result_summary="ok",
        expected_version=run.version,
    )

    events = list_events(db, run.id)
    assert [e.event_type for e in events] == [
        "RunStarted",
        "MetricRecorded",
        "ArtifactAttached",
        "RunCompleted",
    ]

    rebuilt = rebuild_projection_from_events(db, run.id)
    stored = db.get(RunProjection, run.id)
    assert rebuilt is not None and stored is not None
    assert rebuilt.status == stored.status
    assert rebuilt.version == stored.version
    assert rebuilt.dataset_content_sha256 == stored.dataset_content_sha256
    assert rebuilt.code_commit_sha == stored.code_commit_sha
    assert len(rebuilt.metrics_json) == len(stored.metrics_json)
    assert len(rebuilt.artifacts_json) == len(stored.artifacts_json)
    assert rebuilt.artifacts_json[0]["type"] == "log"
    assert stored.artifacts_json[0]["type"] == "log"


def test_illegal_artifact_type_rejected_at_domain(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds-type"),
        code_commit_sha="abc1234",
        description=None,
    )
    version_before = run.version
    events_before = len(list_events(db, run.id))

    with pytest.raises(DomainError) as exc:
        attach_artifact(
            db,
            run_id=run.id,
            actor="researcher",
            name="evil.bin",
            artifact_type="image",
            uri="file:///tmp/evil.bin",
            content_sha256=sha("evil"),
            media_type=None,
            expected_version=version_before,
        )
    assert exc.value.status_code == 422
    assert "产物类型非法" in exc.value.message
    # 非法类型不得产生事件或改动投影版本
    db.rollback()
    stored = db.get(RunProjection, run.id)
    assert stored.version == version_before
    assert len(list_events(db, run.id)) == events_before
    assert all(a.get("name") != "evil.bin" for a in stored.artifacts_json)


def test_all_allowed_artifact_types_accepted(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds-all"),
        code_commit_sha="abc1234",
        description=None,
    )
    for i, t in enumerate(["model", "dataset", "log", "graph"]):
        run = attach_artifact(
            db,
            run_id=run.id,
            actor="researcher",
            name=f"a-{t}",
            artifact_type=t,
            uri=f"file:///tmp/{t}",
            content_sha256=sha(t),
            media_type=None,
            expected_version=run.version,
        )
        assert run.artifacts_json[i]["type"] == t
    assert {a["type"] for a in run.artifacts_json} == set(ARTIFACT_TYPE_LABELS)


def test_schema_rejects_illegal_artifact_type():
    from pydantic import ValidationError

    from app.schemas import AttachArtifactCommand

    base = dict(
        name="x",
        uri="file:///x",
        content_sha256=sha("x"),
        media_type=None,
        expected_version=1,
    )
    # 合法类型通过（Pydantic 归一化为枚举值字符串）
    cmd = AttachArtifactCommand(artifact_type="log", **base)
    assert cmd.artifact_type.value == "log"

    with pytest.raises(ValidationError) as exc:
        AttachArtifactCommand(artifact_type="video", **base)
    assert "产物类型非法" in str(exc.value)

    with pytest.raises(ValidationError):
        AttachArtifactCommand(artifact_type=None, **base)


def test_cannot_command_before_start(db):
    missing = uuid4()
    with pytest.raises(DomainError):
        record_metric(
            db,
            run_id=missing,
            actor="researcher",
            name="x",
            value=1,
            step=0,
            expected_version=0,
        )
