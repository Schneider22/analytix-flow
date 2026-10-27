import { apiClient } from './client';

export type IngestionFormat = 'csv' | 'xlsx' | 'xls';

export interface ArtifactReference {
  artifact_id: string;
  artifact_type: string;
  artifact_version: string;
  version_number: number;
  version_id?: string;
  predecessor_version_id?: string | null;
  content_hash: string;
  uri?: string | null;
  media_type?: string | null;
  layer?: string | null;
  produced_by_module?: string | null;
  created_at?: string | null;
}

export interface M2RequestIdentity {
  executionId: string;
  correlationId: string;
  idempotencyKey: string;
}

export interface M2IngestionOption {
  artifact_id: string;
  format: IngestionFormat;
  encoding?: string;
  delimiter?: string;
  sheet_name?: string;
  header_row?: number;
  date_interpretation?: string;
}

export interface M2IngestionRequest {
  project_id: string;
  execution_id: string;
  module_id: 'm2';
  contract_version: string;
  context_snapshot_id: string;
  status: 'requested';
  correlation_id: string;
  idempotency_key: string;
  module_input: {
    selected_alternative_id: string;
    source_artifacts: ArtifactReference[];
    ingestion_options: M2IngestionOption[];
  };
}

export interface M2ProfileColumn {
  name: string;
  dtype: string;
  missing_count: number;
  unique_count: number;
  null_ratio: number;
}

export interface M2ProfileReport {
  structures?: string[];
  row_count?: number;
  column_count?: number;
  columns?: M2ProfileColumn[];
  temporal_coverage?: Record<string, unknown>;
  potential_identifiers?: string[];
}

export interface M2Issue {
  issue_id?: string;
  severity?: string;
  description?: string;
  requires_human_decision?: boolean;
}

export interface M2SourceManifestItem {
  source_artifact?: ArtifactReference;
  preserved?: boolean;
  content_hash?: string;
  metadata?: Record<string, unknown>;
}

export interface M2ModuleOutput {
  bronze_dataset?: ArtifactReference;
  source_manifest?: M2SourceManifestItem[];
  profile_report?: M2ProfileReport;
  issues?: M2Issue[];
  recovery_options?: Array<Record<string, unknown>>;
}

export interface M2IngestionResult {
  project_id: string;
  execution_id: string;
  module_id: string;
  contract_version: string;
  context_snapshot_id: string;
  correlation_id: string;
  status: string;
  warnings?: string[];
  errors?: Array<Record<string, unknown>>;
  artifacts?: ArtifactReference[];
  module_output?: M2ModuleOutput;
}

export interface RunM2Options {
  contextSnapshotId: string;
  selectedAlternativeId: string;
  sourceArtifact: ArtifactReference;
  format: IngestionFormat;
  identity: M2RequestIdentity;
}

function createRequestId(prefix: string): string {
  const uuid = typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${uuid}`;
}

export function createM2RequestIdentity(): M2RequestIdentity {
  return {
    executionId: createRequestId('m2-execution'),
    correlationId: createRequestId('corr'),
    idempotencyKey: createRequestId('m2-key'),
  };
}

export function getIngestionFormat(fileName: string): IngestionFormat | null {
  const extension = fileName.toLowerCase().split('.').pop();
  if (extension === 'csv' || extension === 'xlsx' || extension === 'xls') {
    return extension;
  }
  return null;
}

function defaultMediaType(format: IngestionFormat): string {
  if (format === 'csv') return 'text/csv';
  if (format === 'xlsx') return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  return 'application/vnd.ms-excel';
}

export async function uploadSourceArtifact(
  projectId: string,
  file: Blob,
  format: IngestionFormat,
): Promise<ArtifactReference> {
  const mediaType = file.type || defaultMediaType(format);
  return apiClient.post<ArtifactReference>(
    `/projects/${encodeURIComponent(projectId)}/artifacts/content`,
    file,
    {
      params: {
        artifact_type: 'source',
        artifact_version: 'v1',
        artifact_id: createRequestId('source'),
        media_type: mediaType,
        layer: 'source',
      },
      headers: { 'Content-Type': mediaType },
    },
  );
}

export function toContractArtifactReference(artifact: ArtifactReference): ArtifactReference {
  const reference: ArtifactReference = {
    artifact_id: artifact.artifact_id,
    artifact_type: artifact.artifact_type,
    artifact_version: artifact.artifact_version,
    version_number: artifact.version_number ?? 1,
    content_hash: artifact.content_hash,
  };
  if (artifact.version_id) reference.version_id = artifact.version_id;
  if (artifact.predecessor_version_id !== undefined) reference.predecessor_version_id = artifact.predecessor_version_id;
  if (artifact.uri !== undefined) reference.uri = artifact.uri;
  if (artifact.media_type !== undefined) reference.media_type = artifact.media_type;
  if (artifact.layer !== undefined) reference.layer = artifact.layer;
  if (artifact.produced_by_module !== undefined) reference.produced_by_module = artifact.produced_by_module;
  if (artifact.created_at !== undefined) reference.created_at = artifact.created_at;
  return reference;
}

export async function runM2(
  projectId: string,
  options: RunM2Options,
): Promise<M2IngestionResult> {
  const sanitizedSource = toContractArtifactReference(options.sourceArtifact);
  const payload: M2IngestionRequest = {
    project_id: projectId,
    execution_id: options.identity.executionId,
    module_id: 'm2',
    contract_version: 'v1.0',
    context_snapshot_id: options.contextSnapshotId,
    status: 'requested',
    correlation_id: options.identity.correlationId,
    idempotency_key: options.identity.idempotencyKey,
    module_input: {
      selected_alternative_id: options.selectedAlternativeId,
      source_artifacts: [sanitizedSource],
      ingestion_options: [
        {
          artifact_id: sanitizedSource.artifact_id,
          format: options.format,
        },
      ],
    },
  };

  return apiClient.post<M2IngestionResult>(
    `/projects/${encodeURIComponent(projectId)}/executions/m2`,
    payload,
  );
}
