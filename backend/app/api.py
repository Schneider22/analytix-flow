from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Query, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .core.config import Settings
from .db.models import Artifact, Approval, AuditEvent, Decision, Project, ProjectContextSnapshot
from .db.session import build_engine, build_session_factory
from .repositories import (
    ApprovalRepository,
    ArtifactRepository,
    AuditRepository,
    DecisionRepository,
    ProjectRepository,
)
from .schemas import (
    ApprovalCreate,
    ApprovalRead,
    ApprovalResolve,
    ArtifactCreate,
    ArtifactRead,
    ArtifactReferenceInput,
    AuditEventRead,
    ContextCreate,
    ContextRead,
    DecisionCreate,
    DecisionRead,
    HealthRead,
    M2IngestionRequest,
    M3PreparationRequest,
    M4ModelingRequest,
    M5EvaluationRequest,
    M6DeploymentRequest,
    M7GovernanceRequest,
    M8DashboardInput,
    ProjectCreate,
    ProjectArchiveRequest,
    ProjectRead,
    ProjectRestoreRequest,
)
from .services import (
    ConflictError,
    NotFoundError,
    ValidationError,
    create_approval,
    create_artifact,
    create_context_snapshot,
    create_decision,
    create_project,
    archive_project,
    require_editable_project,
    require_project,
    restore_project,
    resolve_approval,
)
from .storage import (
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactStorePathError,
    ArtifactTooLargeError,
    LocalArtifactStore,
)
from .orchestrator import ProjectOrchestrator


logger = logging.getLogger("analytixflow.api")

project_repository = ProjectRepository()
artifact_repository = ArtifactRepository()
decision_repository = DecisionRepository()
approval_repository = ApprovalRepository()
audit_repository = AuditRepository()


def get_db(request: Request) -> Generator[Session, None, None]:
    db: Session = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def _context_read(snapshot: ProjectContextSnapshot) -> ContextRead:
    return ContextRead(
        id=snapshot.id,
        project_id=snapshot.project_id,
        version=snapshot.version,
        predecessor_id=snapshot.predecessor_id,
        context=snapshot.context_data,
        content_hash=snapshot.content_hash,
        created_by=snapshot.created_by,
        created_at=snapshot.created_at,
    )


def _artifact_read(artifact: Artifact) -> ArtifactRead:
    return ArtifactRead(
        artifact_id=artifact.logical_id,
        project_id=artifact.project_id,
        version_id=artifact.id,
        artifact_type=artifact.artifact_type,
        artifact_version=artifact.artifact_version,
        version_number=artifact.version_number,
        legacy_version=artifact.legacy_version,
        predecessor_version_id=artifact.predecessor_artifact_id,
        predecessor_artifact_id=(artifact.predecessor.logical_id if artifact.predecessor else None),
        content_hash=artifact.content_hash,
        storage_id=artifact.storage_id,
        uri=artifact.uri or "",
        media_type=artifact.media_type,
        layer=artifact.layer,
        produced_by_module=artifact.produced_by_module,
        source_execution_id=artifact.source_execution_id,
        parent_artifact_ids=artifact.parent_artifact_ids,
        metadata=artifact.metadata_json,
        created_at=artifact.created_at,
    )


def _decision_read(decision: Decision) -> DecisionRead:
    refs = [
        ArtifactReferenceInput(
            artifact_id=link.artifact.logical_id,
            artifact_version=link.artifact.artifact_version,
        )
        for link in decision.evidence_links
    ]
    return DecisionRead(
        id=decision.id,
        project_id=decision.project_id,
        decision_type=decision.decision_type,
        question=decision.question,
        options=decision.options,
        selected_option=decision.selected_option,
        rationale=decision.rationale,
        evidence_artifact_ids=decision.evidence_artifact_ids,
        evidence_artifact_refs=refs,
        status=decision.status,
        decided_by=decision.decided_by,
        decided_at=decision.decided_at,
        created_at=decision.created_at,
    )


def _approval_read(approval: Approval) -> ApprovalRead:
    return ApprovalRead(
        id=approval.id,
        project_id=approval.project_id,
        action=approval.action,
        scope_type=approval.scope_type,
        status=approval.status,
        artifact_id=approval.artifact.logical_id if approval.artifact else None,
        artifact_version=approval.artifact_version,
        execution_id=approval.execution_id,
        decision_id=approval.decision_id,
        scope_hash=approval.scope_hash,
        requested_by=approval.requested_by,
        resolved_by=approval.resolved_by,
        reason=approval.reason,
        created_at=approval.created_at,
        resolved_at=approval.resolved_at,
    )


def _audit_read(event: AuditEvent) -> AuditEventRead:
    return AuditEventRead(
        id=event.id,
        project_id=event.project_id,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        module_id=event.module_id,
        input_hash=event.input_hash,
        output_hash=event.output_hash,
        correlation_id=event.correlation_id,
        metadata=event.metadata_json,
        created_at=event.created_at,
    )


def create_app(settings: Settings | None = None, *, engine=None, session_factory=None) -> FastAPI:
    settings = settings or Settings.from_env()
    engine = engine or build_engine(settings.database_url)
    session_factory = session_factory or build_session_factory(engine)

    app = FastAPI(title="AnalytixFlow API", version="0.1.0")
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.artifact_store = LocalArtifactStore(
        settings.artifact_store_path, max_bytes=settings.max_artifact_bytes
    )
    app.state.orchestrator = ProjectOrchestrator()
    router = APIRouter(prefix=settings.api_prefix)

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        if len(correlation_id) > settings.max_correlation_id_length or any(
            ord(character) < 32 for character in correlation_id
        ):
            return JSONResponse(status_code=422, content={"detail": "Invalid correlation id"})
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_request: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_handler(_request: Request, exc: ValidationError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(SQLAlchemyError)
    async def database_handler(_request: Request, exc: SQLAlchemyError):
        logger.exception("Database persistence error encountered: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Persistence service unavailable"})

    @app.exception_handler(Exception)
    async def unexpected_handler(_request: Request, exc: Exception):
        logger.exception("Unhandled server error encountered: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @router.get("/health", response_model=HealthRead)
    def health(db: Session = Depends(get_db)):
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return HealthRead(status="degraded", database="unavailable")
        return HealthRead(status="ok", database="ok")

    @router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
    def create_project_endpoint(request: Request, payload: ProjectCreate, db: Session = Depends(get_db)):
        return create_project(db, payload, correlation_id=request.state.correlation_id)

    @router.get("/projects", response_model=list[ProjectRead])
    def list_projects(
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        archived: Literal["exclude", "only", "include"] = Query(default="exclude"),
        db: Session = Depends(get_db),
    ):
        return project_repository.list(db, limit=limit, offset=offset, archived=archived)

    @router.get("/projects/{project_id}", response_model=ProjectRead)
    def get_project(project_id: str, db: Session = Depends(get_db)):
        project = project_repository.get(db, project_id)
        if project is None:
            raise NotFoundError("Project not found")
        return project

    @router.post("/projects/{project_id}/archive", response_model=ProjectRead)
    def archive_project_endpoint(
        project_id: str,
        request: Request,
        payload: ProjectArchiveRequest,
        db: Session = Depends(get_db),
    ):
        return archive_project(
            db, project_id, payload, correlation_id=request.state.correlation_id
        )

    @router.post("/projects/{project_id}/restore", response_model=ProjectRead)
    def restore_project_endpoint(
        project_id: str,
        request: Request,
        payload: ProjectRestoreRequest,
        db: Session = Depends(get_db),
    ):
        return restore_project(
            db, project_id, payload, correlation_id=request.state.correlation_id
        )

    @router.post("/projects/{project_id}/context", response_model=ContextRead, status_code=status.HTTP_201_CREATED)
    def create_context_endpoint(
        project_id: str, request: Request, payload: ContextCreate, db: Session = Depends(get_db)
    ):
        return _context_read(
            create_context_snapshot(db, project_id, payload, correlation_id=request.state.correlation_id)
        )

    @router.get("/projects/{project_id}/context", response_model=list[ContextRead])
    def list_context(project_id: str, db: Session = Depends(get_db)):
        from .repositories import ContextSnapshotRepository

        require_project(db, project_id)
        return [_context_read(item) for item in ContextSnapshotRepository().list(db, project_id)]

    @router.post("/projects/{project_id}/decisions", response_model=DecisionRead, status_code=status.HTTP_201_CREATED)
    def create_decision_endpoint(
        project_id: str, request: Request, payload: DecisionCreate, db: Session = Depends(get_db)
    ):
        return _decision_read(
            create_decision(db, project_id, payload, correlation_id=request.state.correlation_id)
        )

    @router.get("/projects/{project_id}/decisions", response_model=list[DecisionRead])
    def list_decisions(project_id: str, db: Session = Depends(get_db)):
        require_project(db, project_id)
        return [_decision_read(item) for item in decision_repository.list(db, project_id)]

    @router.post("/projects/{project_id}/artifacts/content", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
    async def create_artifact_content_endpoint(
        project_id: str,
        request: Request,
        artifact_type: str = Query(min_length=1, max_length=128),
        artifact_version: str = Query(pattern=r"^v[1-9][0-9]*$"),
        artifact_id: str | None = Query(default=None, min_length=1, max_length=128),
        media_type: str | None = Query(default=None, max_length=255),
        layer: str | None = Query(default=None, max_length=32),
        produced_by_module: str | None = Query(default=None, max_length=32),
        source_execution_id: str | None = Query(default=None, max_length=128),
        db: Session = Depends(get_db),
    ):
        # Check lifecycle state before writing bytes to the artifact store.
        require_editable_project(db, project_id)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError as exc:
                raise ValidationError("Invalid content length") from exc
            if declared_length < 0 or declared_length > settings.max_artifact_bytes:
                raise ValidationError("Artifact exceeds the configured size limit")
        content = await request.body()
        stored = request.app.state.artifact_store.put(content)
        payload = ArtifactCreate(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            artifact_version=artifact_version,
            content_hash=stored.content_hash,
            storage_id=stored.storage_id,
            media_type=media_type,
            layer=layer,
            produced_by_module=produced_by_module,
            source_execution_id=source_execution_id,
        )
        return _artifact_read(
            create_artifact(
                db,
                project_id,
                payload,
                request.app.state.artifact_store,
                max_metadata_bytes=settings.max_metadata_bytes,
                correlation_id=request.state.correlation_id,
            )
        )

    @router.post("/projects/{project_id}/artifacts", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
    def create_artifact_endpoint(
        project_id: str, request: Request, payload: ArtifactCreate, db: Session = Depends(get_db)
    ):
        return _artifact_read(
            create_artifact(
                db,
                project_id,
                payload,
                request.app.state.artifact_store,
                max_metadata_bytes=settings.max_metadata_bytes,
                correlation_id=request.state.correlation_id,
            )
        )

    @router.get("/projects/{project_id}/artifacts", response_model=list[ArtifactRead])
    def list_artifacts(project_id: str, db: Session = Depends(get_db)):
        require_project(db, project_id)
        return [_artifact_read(item) for item in artifact_repository.list(db, project_id)]

    @router.get("/projects/{project_id}/artifacts/{artifact_id}/{artifact_version}/content")
    def read_artifact_content(
        project_id: str,
        artifact_id: str,
        artifact_version: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        artifact = artifact_repository.get_by_logical_version(
            db, project_id, artifact_id, artifact_version
        )
        if artifact is None:
            raise NotFoundError("Artifact version not found for project")
        try:
            content = request.app.state.artifact_store.read(
                artifact.storage_id,
                expected_hash=artifact.content_hash,
            )
        except (ArtifactNotFoundError, ArtifactStorePathError) as exc:
            raise NotFoundError("Stored artifact not found") from exc
        except (ArtifactIntegrityError, ArtifactTooLargeError) as exc:
            raise ValidationError("Stored artifact integrity validation failed") from exc
        return Response(
            content=content,
            media_type=artifact.media_type or "application/octet-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Artifact-Content-Hash": artifact.content_hash,
                "X-Artifact-Version-ID": artifact.id,
            },
        )

    @router.post("/projects/{project_id}/executions/m2", response_model=dict)
    def run_m2_endpoint(
        project_id: str,
        request: Request,
        payload: M2IngestionRequest,
        db: Session = Depends(get_db),
    ):
        return request.app.state.orchestrator.run_m2(
            db,
            project_id,
            payload,
            request.app.state.artifact_store,
            max_metadata_bytes=settings.max_metadata_bytes,
        )

    @router.post("/projects/{project_id}/executions/m3", response_model=dict)
    def run_m3_endpoint(
        project_id: str,
        request: Request,
        payload: M3PreparationRequest,
        db: Session = Depends(get_db),
    ):
        return request.app.state.orchestrator.run_m3(
            db,
            project_id,
            payload,
            request.app.state.artifact_store,
            max_metadata_bytes=settings.max_metadata_bytes,
        )

    @router.post("/projects/{project_id}/executions/m4", response_model=dict)
    def run_m4_endpoint(
        project_id: str,
        request: Request,
        payload: M4ModelingRequest,
        db: Session = Depends(get_db),
    ):
        return request.app.state.orchestrator.run_m4(
            db,
            project_id,
            payload,
            request.app.state.artifact_store,
            max_metadata_bytes=settings.max_metadata_bytes,
        )

    @router.post("/projects/{project_id}/executions/m5", response_model=dict)
    def run_m5_endpoint(
        project_id: str,
        request: Request,
        payload: M5EvaluationRequest,
        db: Session = Depends(get_db),
    ):
        return request.app.state.orchestrator.run_m5(
            db,
            project_id,
            payload,
            request.app.state.artifact_store,
            max_metadata_bytes=settings.max_metadata_bytes,
        )

    @router.post("/projects/{project_id}/executions/m6", response_model=dict)
    def run_m6_endpoint(
        project_id: str,
        request: Request,
        payload: M6DeploymentRequest,
        db: Session = Depends(get_db),
    ):
        return request.app.state.orchestrator.run_m6(
            db,
            project_id,
            payload,
            request.app.state.artifact_store,
            max_metadata_bytes=settings.max_metadata_bytes,
        )

    @router.post("/projects/{project_id}/executions/m7", response_model=dict)
    def run_m7_endpoint(
        project_id: str,
        request: Request,
        payload: M7GovernanceRequest,
        db: Session = Depends(get_db),
    ):
        return request.app.state.orchestrator.run_m7(
            db,
            project_id,
            payload,
            request.app.state.artifact_store,
            max_metadata_bytes=settings.max_metadata_bytes,
        )

    @router.post("/projects/{project_id}/dashboard", response_model=dict)
    def generate_dashboard_endpoint(
        project_id: str,
        request: Request,
        payload: M8DashboardInput,
        db: Session = Depends(get_db),
    ):
        return request.app.state.orchestrator.generate_dashboard(
            db,
            project_id,
            payload,
            request.app.state.artifact_store,
            max_metadata_bytes=settings.max_metadata_bytes,
        )

    @router.get("/projects/{project_id}/dashboard", response_model=dict)
    def get_dashboard_endpoint(
        project_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        return request.app.state.orchestrator.get_latest_dashboard(
            db,
            project_id,
            request.app.state.artifact_store,
        )

    @router.post("/projects/{project_id}/executions/m8", response_model=dict)
    def run_m8_endpoint(
        project_id: str,
        request: Request,
        payload: M8DashboardInput,
        db: Session = Depends(get_db),
    ):
        return request.app.state.orchestrator.generate_dashboard(
            db,
            project_id,
            payload,
            request.app.state.artifact_store,
            max_metadata_bytes=settings.max_metadata_bytes,
        )

    @router.post("/projects/{project_id}/approvals", response_model=ApprovalRead, status_code=status.HTTP_201_CREATED)
    def create_approval_endpoint(
        project_id: str, request: Request, payload: ApprovalCreate, db: Session = Depends(get_db)
    ):
        return _approval_read(
            create_approval(db, project_id, payload, correlation_id=request.state.correlation_id)
        )

    @router.get("/projects/{project_id}/approvals", response_model=list[ApprovalRead])
    def list_approvals(project_id: str, db: Session = Depends(get_db)):
        require_project(db, project_id)
        return [_approval_read(item) for item in approval_repository.list(db, project_id)]

    @router.post("/projects/{project_id}/approvals/{approval_id}/resolve", response_model=ApprovalRead)
    def resolve_approval_endpoint(
        project_id: str,
        approval_id: str,
        request: Request,
        payload: ApprovalResolve,
        db: Session = Depends(get_db),
    ):
        return _approval_read(
            resolve_approval(db, project_id, approval_id, payload, correlation_id=request.state.correlation_id)
        )

    @router.get("/projects/{project_id}/audit", response_model=list[AuditEventRead])
    def list_audit(project_id: str, db: Session = Depends(get_db)):
        require_project(db, project_id)
        return [_audit_read(item) for item in audit_repository.list(db, project_id)]

    app.include_router(router)
    return app
