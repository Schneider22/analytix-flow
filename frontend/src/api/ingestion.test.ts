import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ArtifactReference,
  M2RequestIdentity,
  runM2,
  uploadSourceArtifact,
} from './ingestion';

describe('Ingestion API Client', () => {
  const originalFetch = globalThis.fetch;
  const identity: M2RequestIdentity = {
    executionId: 'm2-execution-1',
    correlationId: 'corr-m2-1',
    idempotencyKey: 'm2-key-1',
  };
  const sourceArtifact: ArtifactReference = {
    artifact_id: 'orders-source',
    artifact_type: 'source',
    artifact_version: 'v1',
    version_number: 1,
    version_id: 'source-version-1',
    content_hash: `sha256:${'a'.repeat(64)}`,
    media_type: 'text/csv',
    layer: 'source',
  };

  beforeEach(() => vi.restoreAllMocks());

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('uploads raw CSV bytes through the existing source artifact endpoint', async () => {
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;
    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      capturedUrl = String(url);
      capturedInit = init;
      return Promise.resolve(new Response(JSON.stringify(sourceArtifact), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }));
    });

    const file = new Blob(['id,value\n1,10\n'], { type: 'text/csv' });
    const result = await uploadSourceArtifact('project-1', file, 'csv');

    expect(result).toEqual(sourceArtifact);
    expect(capturedUrl).toContain('/api/v1/projects/project-1/artifacts/content?');
    expect(capturedUrl).toContain('artifact_type=source');
    expect(capturedUrl).toContain('artifact_version=v1');
    expect(capturedUrl).toContain('layer=source');
    expect(capturedInit?.method).toBe('POST');
    expect(capturedInit?.body).toBe(file);
    expect((capturedInit?.headers as Record<string, string>)['Content-Type']).toBe('text/csv');
  });

  it('builds the exact M2 execution envelope with project and artifact references', async () => {
    let capturedBody = '';
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedBody = init?.body as string;
      return Promise.resolve(new Response(JSON.stringify({
        project_id: 'project-1',
        execution_id: identity.executionId,
        module_id: 'm2',
        status: 'succeeded',
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));
    });

    await runM2('project-1', {
      contextSnapshotId: 'context-1',
      selectedAlternativeId: 'alternative-a',
      sourceArtifact,
      format: 'csv',
      identity,
    });

    expect(JSON.parse(capturedBody)).toEqual({
      project_id: 'project-1',
      execution_id: 'm2-execution-1',
      module_id: 'm2',
      contract_version: 'v1.0',
      context_snapshot_id: 'context-1',
      status: 'requested',
      correlation_id: 'corr-m2-1',
      idempotency_key: 'm2-key-1',
      module_input: {
        selected_alternative_id: 'alternative-a',
        source_artifacts: [sourceArtifact],
        ingestion_options: [{ artifact_id: 'orders-source', format: 'csv' }],
      },
    });
  });

  it('strips forbidden server-internal fields from source artifact before sending to M2', async () => {
    let capturedBody = '';
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedBody = init?.body as string;
      return Promise.resolve(new Response(JSON.stringify({ status: 'succeeded' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));
    });

    const artifactWithExtraFields = {
      ...sourceArtifact,
      storage_id: 'internal-storage-id',
      project_id: 'project-1',
      metadata: { key: 'val' },
      legacy_version: false,
    } as unknown as ArtifactReference;

    await runM2('project-1', {
      contextSnapshotId: 'context-1',
      selectedAlternativeId: 'alternative-a',
      sourceArtifact: artifactWithExtraFields,
      format: 'csv',
      identity,
    });

    const parsed = JSON.parse(capturedBody);
    const sentArtifact = parsed.module_input.source_artifacts[0];
    expect(sentArtifact.storage_id).toBeUndefined();
    expect(sentArtifact.project_id).toBeUndefined();
    expect(sentArtifact.metadata).toBeUndefined();
    expect(sentArtifact.legacy_version).toBeUndefined();
    expect(sentArtifact.artifact_id).toBe('orders-source');
  });
});
