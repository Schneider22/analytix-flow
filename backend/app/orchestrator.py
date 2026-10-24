from __future__ import annotations

from sqlalchemy.orm import Session

from .m2_ingestion import M2IngestionModule
from .schemas import M2IngestionRequest
from .storage import ArtifactStore


class ProjectOrchestrator:
    """Central entry point for module execution.

    Increment 2 exposes only M2. The module remains isolated behind this
    boundary so later modules cannot invoke one another directly.
    """

    def __init__(self) -> None:
        self._m2 = M2IngestionModule()

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
