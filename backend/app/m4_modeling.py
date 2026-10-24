from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import sys
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from sqlalchemy.orm import Session

from .db.models import Artifact, Execution, Project, ProjectContextSnapshot
from .domain.hashing import canonical_json, sha256_canonical
from .repositories import ExecutionRepository
from .schemas import ArtifactCreate, ArtifactReferenceInput, M4ModelingRequest
from .services import (
    ConflictError,
    NotFoundError,
    ValidationError,
    _verified_storage,
    artifacts,
    commit,
    create_artifact,
    record_audit,
    require_project,
)
from .storage import ArtifactStore, ArtifactStoreError


class M4ModelingModule:
    """Run bounded, reproducible local modeling experiments.

    M4 intentionally emits candidate artifacts and a human approval request;
    it does not select a candidate, evaluate it formally or deploy anything.
    The supported technique vocabulary is explicit so an arbitrary model name
    cannot silently change the execution semantics.
    """

    module_id = "m4"
    contract_version = "v1.0"
    supported_techniques = {
        "classification": frozenset(
            {"logistic_regression", "decision_tree_classifier"}
        ),
        "regression": frozenset({"linear_regression", "decision_tree_regressor"}),
        "descriptive": frozenset({"descriptive_statistics"}),
    }
    baselines = {
        "classification": "majority_class_baseline",
        "regression": "mean_baseline",
    }

    def __init__(self) -> None:
        self.executions = ExecutionRepository()

    def execute(
        self,
        db: Session,
        project_id: str,
        payload: M4ModelingRequest,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict[str, Any]:
        self._validate_request(project_id, payload)
        self._validate_policy(payload)
        project = require_project(db, project_id)
        context = db.get(ProjectContextSnapshot, payload.context_snapshot_id)
        if context is None or context.project_id != project_id:
            raise NotFoundError("Context snapshot not found for project")

        input_hash = sha256_canonical(payload.model_dump(mode="json"))
        locked_project = db.get(Project, project_id, with_for_update=True)
        if locked_project is None:
            raise NotFoundError("Project not found")

        existing = self.executions.get_by_idempotency(
            db, project_id, self.module_id, payload.idempotency_key
        )
        if existing is not None:
            if existing.input_hash != input_hash or existing.id != payload.execution_id:
                raise ConflictError("The idempotency key is already bound to another M4 execution")
            if existing.result_json is not None:
                return existing.result_json
            raise ConflictError("The idempotent M4 execution is already running")

        existing_by_id = self.executions.get(db, payload.execution_id)
        if existing_by_id is not None:
            raise ConflictError("execution_id is already in use")

        now = datetime.now(timezone.utc)
        execution = Execution(
            id=payload.execution_id,
            project_id=project_id,
            module_id=self.module_id,
            contract_version=payload.contract_version,
            context_snapshot_id=context.id,
            status="running",
            idempotency_key=payload.idempotency_key,
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            requested_at=payload.requested_at or now,
            started_at=now,
        )
        self.executions.create(db, execution)
        record_audit(
            db,
            project_id=project_id,
            action="execution.started",
            entity_type="execution",
            entity_id=execution.id,
            module_id=self.module_id,
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            metadata={"contract_version": payload.contract_version},
        )
        commit(db)

        try:
            gold, problem_definition, frame = self._load_inputs(
                db, project_id, payload, artifact_store
            )
            experiment = self._run_experiments(
                frame,
                payload,
                gold=gold,
                problem_definition=problem_definition,
            )
            output = self._persist_outputs(
                db,
                project_id,
                execution,
                payload,
                experiment,
                gold,
                problem_definition,
                artifact_store,
                max_metadata_bytes=max_metadata_bytes,
            )
            return self._persist_output(
                db,
                execution,
                output,
                input_hash=input_hash,
                correlation_id=payload.correlation_id,
            )
        except (ValidationError, NotFoundError, ConflictError) as exc:
            self._fail_execution(db, execution.id, payload, input_hash, str(exc))
            raise
        except ArtifactStoreError as exc:
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Artifact storage failed during M4 modeling",
            )
            raise ValidationError("Artifact storage failed during modeling") from exc
        except Exception as exc:
            self._fail_execution(
                db,
                execution.id,
                payload,
                input_hash,
                "Unexpected M4 modeling failure",
            )
            raise RuntimeError("M4 modeling failed") from exc

    def _validate_request(self, project_id: str, payload: M4ModelingRequest) -> None:
        if payload.project_id != project_id:
            raise ValidationError("project_id in the contract does not match the URL scope")
        if payload.module_id != self.module_id:
            raise ValidationError("M4 execution requires module_id='m4'")
        if payload.contract_version != self.contract_version:
            raise ValidationError("M4 requires contract_version='v1.0'")
        if payload.status not in {"requested", "ready"}:
            raise ValidationError("M4 executions must start in requested or ready status")

    def _validate_policy(self, payload: M4ModelingRequest) -> None:
        module_input = payload.module_input
        problem_type = module_input.model_policy.problem_type
        techniques = [item.strip() for item in module_input.model_policy.allowed_techniques]
        if any(not item for item in techniques) or len(set(techniques)) != len(techniques):
            raise ValidationError("allowed_techniques must contain unique non-empty values")
        unsupported = sorted(
            set(techniques) - self.supported_techniques[problem_type]
        )
        if unsupported:
            raise ValidationError(
                f"Unsupported M4 techniques for {problem_type}: {', '.join(unsupported)}"
            )
        if problem_type == "descriptive" and module_input.target_column is not None:
            raise ValidationError("Descriptive M4 modeling cannot declare target_column")
        if problem_type != "descriptive" and not module_input.target_column:
            raise ValidationError(
                "Classification and regression M4 modeling require target_column"
            )

        split_policy = module_input.split_policy
        if split_policy.strategy == "cross_validation" and split_policy.folds is None:
            raise ValidationError("cross_validation requires split_policy.folds")
        if split_policy.strategy == "temporal_holdout" and not split_policy.time_column:
            raise ValidationError("temporal_holdout requires split_policy.time_column")

    def _load_inputs(
        self,
        db: Session,
        project_id: str,
        payload: M4ModelingRequest,
        artifact_store: ArtifactStore,
    ) -> tuple[Artifact, Artifact, Any]:
        try:
            import pandas as pd
        except ModuleNotFoundError as exc:
            raise ValidationError("pandas is required for M4 modeling") from exc

        gold_ref = payload.module_input.gold_dataset
        problem_ref = payload.module_input.problem_definition
        gold = artifacts.get_by_logical_version(
            db, project_id, gold_ref.artifact_id, gold_ref.artifact_version
        )
        if gold is None:
            raise NotFoundError("Gold dataset artifact not found for project")
        problem_definition = artifacts.get_by_logical_version(
            db, project_id, problem_ref.artifact_id, problem_ref.artifact_version
        )
        if problem_definition is None:
            raise NotFoundError("Problem definition artifact not found for project")
        if gold.id == problem_definition.id:
            raise ValidationError("Gold dataset and problem definition must be different artifacts")

        self._validate_artifact_reference(gold, gold_ref, expected_layer="gold")
        self._validate_artifact_reference(problem_definition, problem_ref)
        if gold.media_type and gold.media_type.split(";", 1)[0].lower() != "text/csv":
            raise ValidationError("M4 currently accepts Gold datasets as CSV artifacts")

        _verified_storage(artifact_store, gold.storage_id, gold.content_hash)
        problem_bytes = artifact_store.read(
            problem_definition.storage_id, expected_hash=problem_definition.content_hash
        )
        self._validate_problem_definition(problem_bytes, payload)
        try:
            frame = pd.read_csv(
                BytesIO(artifact_store.read(gold.storage_id, expected_hash=gold.content_hash))
            )
        except Exception as exc:
            raise ValidationError("Gold dataset could not be read as CSV") from exc
        if frame.empty:
            raise ValidationError("Gold dataset must contain at least one row")
        if frame.columns.duplicated().any():
            raise ValidationError("Gold dataset contains duplicate column names")
        frame.columns = [str(column) for column in frame.columns]
        return gold, problem_definition, frame.reset_index(drop=True)

    @staticmethod
    def _validate_problem_definition(
        problem_bytes: bytes, payload: M4ModelingRequest
    ) -> None:
        try:
            document = json.loads(problem_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Problem definition must be valid UTF-8 JSON") from exc
        if not isinstance(document, dict):
            raise ValidationError("Problem definition must be a JSON object")

        definition = document.get("problem_definition", document)
        if not isinstance(definition, dict):
            raise ValidationError("Problem definition payload is not an object")
        declared_type = definition.get("problem_type")
        expected_type = payload.module_input.model_policy.problem_type
        if declared_type != expected_type:
            raise ValidationError(
                "Problem definition problem_type does not match the M4 model policy"
            )
        declared_target = definition.get("target", definition.get("target_column"))
        requested_target = payload.module_input.target_column
        if declared_target is not None and declared_target != requested_target:
            raise ValidationError(
                "Problem definition target does not match the M4 target_column"
            )

    @staticmethod
    def _validate_artifact_reference(
        artifact: Artifact, reference: Any, *, expected_layer: str | None = None
    ) -> None:
        if artifact.artifact_type != reference.artifact_type:
            raise ValidationError("Artifact reference type does not match the server record")
        if artifact.content_hash != reference.content_hash:
            raise ValidationError("Artifact reference content_hash does not match the server record")
        if artifact.version_number != reference.version_number:
            raise ValidationError("Artifact reference version_number does not match the server record")
        if reference.version_id is not None and artifact.id != reference.version_id:
            raise ValidationError("Artifact reference version_id does not match the server record")
        if expected_layer is not None and artifact.layer != expected_layer:
            raise ValidationError(f"M4 requires a {expected_layer} artifact")

    def _run_experiments(
        self,
        frame: Any,
        payload: M4ModelingRequest,
        *,
        gold: Artifact,
        problem_definition: Artifact,
    ) -> dict[str, Any]:
        policy = payload.module_input.model_policy
        problem_type = policy.problem_type
        target_column = payload.module_input.target_column
        seed = payload.module_input.reproducibility.random_seed
        environment = self._environment_record(
            payload.module_input.reproducibility.record_environment
        )
        if problem_type == "descriptive":
            techniques = ["descriptive_statistics"]
            candidates = [
                self._run_descriptive_candidate(
                    frame,
                    technique=techniques[0],
                    candidate_id=self._candidate_id(payload.execution_id, techniques[0]),
                )
            ]
            split_summary = {
                "strategy": "not_applicable",
                "test_fraction": payload.module_input.split_policy.test_fraction,
            }
        else:
            assert target_column is not None
            if target_column not in frame.columns:
                raise ValidationError(f"target_column {target_column!r} is not present in Gold")
            if frame[target_column].isna().any():
                raise ValidationError(
                    "M4 cannot silently discard rows with missing target values; prepare Gold first"
                )
            features = frame.drop(columns=[target_column])
            if features.shape[1] == 0:
                raise ValidationError("M4 requires at least one feature column besides target_column")
            target = frame[target_column]
            if problem_type == "classification":
                if target.nunique(dropna=True) < 2:
                    raise ValidationError("Classification requires at least two target classes")
            else:
                numeric_target = pd_to_numeric(target)
                target = numeric_target
            splits, split_summary = self._build_splits(
                frame,
                target,
                payload,
                problem_type=problem_type,
            )
            techniques = [self.baselines[problem_type]] + [
                technique
                for technique in policy.allowed_techniques
                if technique != self.baselines[problem_type]
            ]
            candidates = [
                self._run_supervised_candidate(
                    features,
                    target,
                    splits,
                    technique=technique,
                    problem_type=problem_type,
                    seed=seed,
                    candidate_id=self._candidate_id(payload.execution_id, technique),
                )
                for technique in techniques
            ]
            baseline = candidates[0]["preliminary_results"]
            baseline_metric_name = baseline["primary_metric"]
            baseline_value = baseline["metrics"][baseline_metric_name]
            for candidate in candidates:
                preliminary = candidate["preliminary_results"]
                candidate_value = preliminary["metrics"][baseline_metric_name]
                direction = "higher_is_better" if problem_type == "classification" else "lower_is_better"
                delta = (
                    candidate_value - baseline_value
                    if direction == "higher_is_better"
                    else baseline_value - candidate_value
                )
                preliminary["baseline_comparison"] = {
                    "baseline_candidate_id": candidates[0]["candidate_id"],
                    "metric": baseline_metric_name,
                    "baseline_value": baseline_value,
                    "candidate_value": candidate_value,
                    "improvement_over_baseline": delta,
                    "direction": direction,
                }

        candidate_ids = [candidate["candidate_id"] for candidate in candidates]
        return {
            "gold_dataset": self._artifact_reference(gold),
            "problem_definition": self._artifact_reference(problem_definition),
            "problem_type": problem_type,
            "target_column": target_column,
            "model_policy": policy.model_dump(mode="json"),
            "split_policy": payload.module_input.split_policy.model_dump(mode="json"),
            "reproducibility": payload.module_input.reproducibility.model_dump(mode="json"),
            "split_summary": split_summary,
            "environment": environment,
            "candidates": candidates,
            "candidate_ids": candidate_ids,
        }

    def _build_splits(
        self,
        frame: Any,
        target: Any,
        payload: M4ModelingRequest,
        *,
        problem_type: str,
    ) -> tuple[list[tuple[Any, Any]], dict[str, Any]]:
        from sklearn.model_selection import (
            KFold,
            StratifiedKFold,
            train_test_split,
        )

        policy = payload.module_input.split_policy
        indices = list(range(len(frame.index)))
        if len(indices) < 2:
            raise ValidationError("M4 supervised modeling requires at least two rows")
        if policy.strategy == "holdout":
            stratify = None
            if problem_type == "classification":
                counts = target.value_counts(dropna=False)
                if counts.min() < 2:
                    raise ValidationError(
                        "Holdout classification requires at least two rows per target class"
                    )
                stratify = target
            train, test = train_test_split(
                indices,
                test_size=policy.test_fraction,
                random_state=payload.module_input.reproducibility.random_seed,
                shuffle=True,
                stratify=stratify,
            )
            if not train or not test:
                raise ValidationError("The holdout split must contain train and test rows")
            return [(train, test)], {
                "strategy": policy.strategy,
                "test_fraction": policy.test_fraction,
                "folds": 1,
                "train_rows": len(train),
                "test_rows": len(test),
            }

        if policy.strategy == "cross_validation":
            assert policy.folds is not None
            if policy.folds >= len(indices):
                raise ValidationError("cross_validation.folds must be smaller than row count")
            if problem_type == "classification":
                counts = target.value_counts(dropna=False)
                if counts.min() < policy.folds:
                    raise ValidationError(
                        "Each classification target class must have at least folds rows"
                    )
                splitter = StratifiedKFold(
                    n_splits=policy.folds,
                    shuffle=True,
                    random_state=payload.module_input.reproducibility.random_seed,
                )
                splits = list(splitter.split(frame, target))
            else:
                splitter = KFold(
                    n_splits=policy.folds,
                    shuffle=True,
                    random_state=payload.module_input.reproducibility.random_seed,
                )
                splits = list(splitter.split(frame))
            return [(train, test) for train, test in splits], {
                "strategy": policy.strategy,
                "test_fraction": policy.test_fraction,
                "folds": policy.folds,
                "train_rows_per_fold": len(splits[0][0]),
                "test_rows_per_fold": len(splits[0][1]),
            }

        assert policy.time_column is not None
        if policy.time_column not in frame.columns:
            raise ValidationError(f"time_column {policy.time_column!r} is not present in Gold")
        parsed_time = frame[policy.time_column].map(lambda value: value)
        parsed_time = to_datetime(parsed_time)
        if parsed_time.isna().any():
            raise ValidationError("temporal_holdout requires every time_column value to be parseable")
        ordered = parsed_time.sort_values(kind="mergesort").index.tolist()
        test_count = max(1, math.ceil(len(ordered) * policy.test_fraction))
        if test_count >= len(ordered):
            raise ValidationError("temporal_holdout must leave at least one training row")
        train = ordered[:-test_count]
        test = ordered[-test_count:]
        return [(train, test)], {
            "strategy": policy.strategy,
            "test_fraction": policy.test_fraction,
            "folds": 1,
            "train_rows": len(train),
            "test_rows": len(test),
            "time_column": policy.time_column,
            "ordered_by_time": True,
        }

    def _run_supervised_candidate(
        self,
        features: Any,
        target: Any,
        splits: list[tuple[Any, Any]],
        *,
        technique: str,
        problem_type: str,
        seed: int,
        candidate_id: str,
    ) -> dict[str, Any]:
        reports: list[dict[str, float]] = []
        for train_indices, test_indices in splits:
            pipeline = self._build_pipeline(features, technique, problem_type, seed)
            pipeline.fit(features.iloc[train_indices], target.iloc[train_indices])
            predictions = pipeline.predict(features.iloc[test_indices])
            reports.append(
                self._metrics(problem_type, target.iloc[test_indices], predictions)
            )
        final_pipeline = self._build_pipeline(features, technique, problem_type, seed)
        final_pipeline.fit(features, target)
        metric_names = sorted(reports[0])
        metrics = {
            name: float(sum(report[name] for report in reports) / len(reports))
            for name in metric_names
        }
        metric_std = {
            name: float(
                (sum((report[name] - metrics[name]) ** 2 for report in reports) / len(reports))
                ** 0.5
            )
            for name in metric_names
        }
        primary_metric = "f1_macro" if problem_type == "classification" else "rmse"
        return {
            "candidate_id": candidate_id,
            "technique": technique,
            "pipeline_bytes": self._serialize_pipeline(final_pipeline),
            "parameter_payload": {
                "format": "sklearn_pipeline_joblib",
                "technique": technique,
                "problem_type": problem_type,
                "feature_columns": [str(column) for column in features.columns],
                "random_seed": seed,
                "preprocessing": "numeric and categorical imputation plus one-hot encoding",
            },
            "preliminary_results": {
                "result_classification": "measured",
                "metrics": metrics,
                "metric_std": metric_std,
                "primary_metric": primary_metric,
                "train_rows": sum(len(train) for train, _ in splits),
                "test_rows": sum(len(test) for _, test in splits),
                "fold_count": len(splits),
                "limitations": [
                    "Preliminary metrics are not formal evaluation and must be reviewed by M5.",
                    "Model candidate artifacts are local joblib binaries and should not be loaded from untrusted sources.",
                ],
            },
            "limitations": [
                "Preliminary metrics are not formal evaluation and must be reviewed by M5.",
                "Model candidate artifacts are local joblib binaries and should not be loaded from untrusted sources.",
            ],
        }

    def _run_descriptive_candidate(
        self, frame: Any, *, technique: str, candidate_id: str
    ) -> dict[str, Any]:
        profile = {
            "row_count": int(len(frame.index)),
            "column_count": int(len(frame.columns)),
            "columns": [
                {
                    "name": str(column),
                    "dtype": str(frame[column].dtype),
                    "missing_count": int(frame[column].isna().sum()),
                    "unique_count": int(frame[column].nunique(dropna=True)),
                }
                for column in frame.columns
            ],
        }
        spec = {
            "format": "descriptive_model_spec",
            "technique": technique,
            "profile": profile,
        }
        limitations = [
            "Descriptive output is not a predictive model and has no effectiveness metric.",
            "Formal business interpretation remains outside M4 and requires human review.",
        ]
        return {
            "candidate_id": candidate_id,
            "technique": technique,
            "pipeline_bytes": canonical_json(spec).encode("utf-8"),
            "parameter_payload": spec,
            "preliminary_results": {
                "result_classification": "measured",
                "profile": profile,
                "primary_metric": "row_count",
                "metrics": {"row_count": profile["row_count"], "column_count": profile["column_count"]},
                "limitations": limitations,
            },
            "limitations": limitations,
        }

    @staticmethod
    def _build_pipeline(features: Any, technique: str, problem_type: str, seed: int):
        from sklearn.compose import ColumnTransformer
        from sklearn.dummy import DummyClassifier, DummyRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LinearRegression, LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
        from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

        numeric = list(features.select_dtypes(include=["number"]).columns)
        categorical = [column for column in features.columns if column not in numeric]
        transformers = []
        if numeric:
            numeric_steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="constant", fill_value=0))]
            if technique in {"logistic_regression", "linear_regression"}:
                numeric_steps.append(("scaler", StandardScaler()))
            transformers.append(
                ("numeric", Pipeline(numeric_steps), numeric)
            )
        if categorical:
            transformers.append(
                (
                    "categorical",
                    Pipeline(
                        [
                            ("imputer", SimpleImputer(strategy="constant", fill_value="__missing__")),
                            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                        ]
                    ),
                    categorical,
                )
            )
        if not transformers:
            raise ValidationError("M4 found no usable feature columns")
        preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")
        if technique == "logistic_regression":
            estimator = LogisticRegression(max_iter=500, random_state=seed)
        elif technique == "decision_tree_classifier":
            estimator = DecisionTreeClassifier(max_depth=5, random_state=seed)
        elif technique == "linear_regression":
            estimator = LinearRegression()
        elif technique == "decision_tree_regressor":
            estimator = DecisionTreeRegressor(max_depth=5, random_state=seed)
        elif technique == "majority_class_baseline":
            estimator = DummyClassifier(strategy="most_frequent")
        elif technique == "mean_baseline":
            estimator = DummyRegressor(strategy="mean")
        else:
            raise ValidationError(f"Unsupported M4 candidate technique: {technique}")
        return Pipeline([("preprocess", preprocessor), ("model", estimator)])

    @staticmethod
    def _metrics(problem_type: str, actual: Any, predicted: Any) -> dict[str, float]:
        if problem_type == "classification":
            from sklearn.metrics import accuracy_score, f1_score

            return {
                "accuracy": float(accuracy_score(actual, predicted)),
                "f1_macro": float(f1_score(actual, predicted, average="macro", zero_division=0)),
            }
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        return {
            "mae": float(mean_absolute_error(actual, predicted)),
            "rmse": float(math.sqrt(mean_squared_error(actual, predicted))),
            "r2": float(r2_score(actual, predicted)),
        }

    def _persist_outputs(
        self,
        db: Session,
        project_id: str,
        execution: Execution,
        payload: M4ModelingRequest,
        experiment: dict[str, Any],
        gold: Artifact,
        problem_definition: Artifact,
        artifact_store: ArtifactStore,
        *,
        max_metadata_bytes: int,
    ) -> dict[str, Any]:
        experiment_id = self._candidate_id(execution.id, "experiment")
        experiment_payload = {
            "execution_id": execution.id,
            "contract_version": payload.contract_version,
            "gold_dataset": experiment["gold_dataset"],
            "problem_definition": experiment["problem_definition"],
            "problem_type": experiment["problem_type"],
            "target_column": experiment["target_column"],
            "model_policy": experiment["model_policy"],
            "split_policy": experiment["split_policy"],
            "split_summary": experiment["split_summary"],
            "reproducibility": experiment["reproducibility"],
            "environment": experiment["environment"],
            "candidate_ids": experiment["candidate_ids"],
        }
        experiment_stored = artifact_store.put(canonical_json(experiment_payload).encode("utf-8"))
        experiment_artifact = create_artifact(
            db,
            project_id,
            ArtifactCreate(
                artifact_id=experiment_id,
                artifact_type="experiment.m4",
                artifact_version="v1",
                content_hash=experiment_stored.content_hash,
                storage_id=experiment_stored.storage_id,
                uri=experiment_stored.uri,
                media_type="application/json",
                layer="model",
                produced_by_module=self.module_id,
                source_execution_id=execution.id,
                parent_artifact_refs=[
                    ArtifactReferenceInput(
                        artifact_id=gold.logical_id, artifact_version=gold.artifact_version
                    ),
                    ArtifactReferenceInput(
                        artifact_id=problem_definition.logical_id,
                        artifact_version=problem_definition.artifact_version,
                    ),
                ],
                metadata={"candidate_count": len(experiment["candidates"])},
            ),
            artifact_store,
            max_metadata_bytes=max_metadata_bytes,
            correlation_id=payload.correlation_id,
            commit_transaction=False,
        )

        experiment_ref = self._artifact_reference(experiment_artifact)
        candidates: list[dict[str, Any]] = []
        all_artifact_refs = [experiment_ref]
        for candidate in experiment["candidates"]:
            parents = [
                ArtifactReferenceInput(
                    artifact_id=experiment_artifact.logical_id,
                    artifact_version=experiment_artifact.artifact_version,
                )
            ]
            pipeline_stored = artifact_store.put(candidate["pipeline_bytes"])
            pipeline = create_artifact(
                db,
                project_id,
                ArtifactCreate(
                    artifact_id=f"{candidate['candidate_id']}-pipeline",
                    artifact_type="model.pipeline",
                    artifact_version="v1",
                    content_hash=pipeline_stored.content_hash,
                    storage_id=pipeline_stored.storage_id,
                    uri=pipeline_stored.uri,
                    media_type=(
                        "application/octet-stream"
                        if experiment["problem_type"] != "descriptive"
                        else "application/json"
                    ),
                    layer="model",
                    produced_by_module=self.module_id,
                    source_execution_id=execution.id,
                    parent_artifact_refs=parents,
                    metadata={"candidate_id": candidate["candidate_id"]},
                ),
                artifact_store,
                max_metadata_bytes=max_metadata_bytes,
                correlation_id=payload.correlation_id,
                commit_transaction=False,
            )
            parameter_stored = artifact_store.put(
                canonical_json(candidate["parameter_payload"]).encode("utf-8")
            )
            parameters = create_artifact(
                db,
                project_id,
                ArtifactCreate(
                    artifact_id=f"{candidate['candidate_id']}-parameters",
                    artifact_type="model.parameters",
                    artifact_version="v1",
                    content_hash=parameter_stored.content_hash,
                    storage_id=parameter_stored.storage_id,
                    uri=parameter_stored.uri,
                    media_type="application/json",
                    layer="model",
                    produced_by_module=self.module_id,
                    source_execution_id=execution.id,
                    parent_artifact_refs=parents,
                    metadata={"candidate_id": candidate["candidate_id"]},
                ),
                artifact_store,
                max_metadata_bytes=max_metadata_bytes,
                correlation_id=payload.correlation_id,
                commit_transaction=False,
            )
            pipeline_ref = self._artifact_reference(pipeline)
            parameter_ref = self._artifact_reference(parameters)
            all_artifact_refs.extend([pipeline_ref, parameter_ref])
            candidates.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "technique": candidate["technique"],
                    "pipeline_artifact": pipeline_ref,
                    "parameter_artifact": parameter_ref,
                    "preliminary_results": candidate["preliminary_results"],
                    "limitations": candidate["limitations"],
                }
            )

        module_output = {
            "experiment_artifacts": [experiment_ref],
            "candidates": candidates,
            "selection_request": {
                "action": "select_model_candidate",
                "candidate_ids": [item["candidate_id"] for item in candidates],
                "requires_approval": True,
            },
        }
        return self._result_envelope(
            payload,
            status="succeeded",
            artifacts=all_artifact_refs,
            warnings=payload.warnings,
            errors=[],
            next_actions=[
                {
                    "action": "select_model_candidate",
                    "requires_approval": True,
                    "target_module": "m5",
                }
            ],
            module_output=module_output,
        )

    @staticmethod
    def _serialize_pipeline(pipeline: Any) -> bytes:
        try:
            import joblib

            buffer = BytesIO()
            joblib.dump(pipeline, buffer, compress=3)
            return buffer.getvalue()
        except ModuleNotFoundError as exc:
            raise ValidationError("scikit-learn and joblib are required for M4 modeling") from exc

    @staticmethod
    def _environment_record(record: bool) -> dict[str, Any]:
        if not record:
            return {"recorded": False}

        def package_version(name: str) -> str:
            try:
                return importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                return "unavailable"

        return {
            "recorded": True,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pandas": package_version("pandas"),
            "scikit_learn": package_version("scikit-learn"),
        }

    @staticmethod
    def _candidate_id(execution_id: str, technique: str) -> str:
        digest = hashlib.sha256(execution_id.encode("utf-8")).hexdigest()[:16]
        safe_technique = "".join(character if character.isalnum() else "-" for character in technique)
        return f"m4-{safe_technique}-{digest}"

    @staticmethod
    def _artifact_reference(artifact: Artifact) -> dict[str, Any]:
        reference = {
            "artifact_id": artifact.logical_id,
            "artifact_type": artifact.artifact_type,
            "artifact_version": artifact.artifact_version,
            "version_number": artifact.version_number,
            "version_id": artifact.id,
            "content_hash": artifact.content_hash,
        }
        optional = {
            "predecessor_version_id": artifact.predecessor_artifact_id,
            "uri": artifact.uri,
            "media_type": artifact.media_type,
            "layer": artifact.layer,
            "produced_by_module": artifact.produced_by_module,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        }
        reference.update({key: value for key, value in optional.items() if value is not None})
        return reference

    @staticmethod
    def _result_envelope(
        payload: M4ModelingRequest,
        *,
        status: str,
        artifacts: list[dict[str, Any]],
        warnings: list[str],
        errors: list[dict[str, Any]],
        next_actions: list[dict[str, Any]],
        module_output: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "project_id": payload.project_id,
            "execution_id": payload.execution_id,
            "module_id": "m4",
            "contract_version": payload.contract_version,
            "context_snapshot_id": payload.context_snapshot_id,
            "correlation_id": payload.correlation_id,
            "status": status,
            "artifacts": artifacts,
            "approval_refs": [
                reference.model_dump(mode="json", exclude_none=True)
                for reference in payload.approval_refs
            ],
            "warnings": warnings,
            "errors": errors,
            "next_actions": next_actions,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "module_output": module_output,
        }

    def _persist_output(
        self,
        db: Session,
        execution: Execution,
        output: dict[str, Any],
        *,
        input_hash: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        execution.status = output["status"]
        execution.output_hash = sha256_canonical(output)
        execution.result_json = output
        execution.completed_at = datetime.now(timezone.utc)
        record_audit(
            db,
            project_id=execution.project_id,
            action="execution.completed",
            entity_type="execution",
            entity_id=execution.id,
            module_id=self.module_id,
            correlation_id=correlation_id,
            input_hash=input_hash,
            output_hash=execution.output_hash,
            metadata={"status": output["status"]},
        )
        commit(db)
        return output

    def _fail_execution(
        self,
        db: Session,
        execution_id: str,
        payload: M4ModelingRequest,
        input_hash: str,
        message: str,
    ) -> None:
        db.rollback()
        execution = self.executions.get(db, execution_id)
        if execution is None:
            return
        execution.status = "failed_terminal"
        execution.error_summary = message[:1000]
        execution.completed_at = datetime.now(timezone.utc)
        record_audit(
            db,
            project_id=execution.project_id,
            action="execution.failed",
            entity_type="execution",
            entity_id=execution.id,
            module_id=self.module_id,
            correlation_id=payload.correlation_id,
            input_hash=input_hash,
            metadata={"status": "failed_terminal", "error": "M4 modeling failed"},
        )
        commit(db)


def pd_to_numeric(series: Any) -> Any:
    import pandas as pd

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        raise ValidationError("Regression target_column must contain only numeric values")
    return numeric


def to_datetime(series: Any) -> Any:
    import pandas as pd

    return pd.to_datetime(series, errors="coerce", format="mixed")
