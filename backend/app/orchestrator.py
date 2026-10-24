from __future__ import annotations

from sqlalchemy.orm import Session

from .m2_ingestion import M2IngestionModule
from .m3_preparation import M3PreparationModule
from .m4_modeling import M4ModelingModule
from .m5_evaluation import M5EvaluationModule
from .m6_deployment import M6DeploymentModule
from .schemas import (
    M2IngestionRequest,
    M3PreparationRequest,
    M4ModelingRequest,
    M5EvaluationRequest,
    M6DeploymentRequest,
)
from .storage import ArtifactStore


class ProjectOrchestrator:
    """Central entry point for module execution.

    Modules remain isolated behind this boundary so no module can invoke
    another module directly.
    """

    def __init__(self) -> None:
        self._m2 = M2IngestionModule()
        self._m3 = M3PreparationModule()
        self._m4 = M4ModelingModule()
        self._m5 = M5EvaluationModule()
        self._m6 = M6DeploymentModule()

    def run_m2(
        self,
        db: Session,
        project_id: str,
        payload: M2IngestionRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m2.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def run_m3(
        self,
        db: Session,
        project_id: str,
        payload: M3PreparationRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m3.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def run_m4(
        self,
        db: Session,
        project_id: str,
        payload: M4ModelingRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m4.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def run_m5(
        self,
        db: Session,
        project_id: str,
        payload: M5EvaluationRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m5.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )

    def run_m6(
        self,
        db: Session,
        project_id: str,
        payload: M6DeploymentRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict:
        return self._m6.execute(
            db,
            project_id,
            payload,
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
        )
