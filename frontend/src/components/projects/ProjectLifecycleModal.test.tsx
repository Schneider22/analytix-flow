import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProjectLifecycleModal } from './ProjectLifecycleModal';
import { ProjectRead } from '../../types/projects';

const project: ProjectRead = {
  id: 'project-1',
  company_name: 'Empresa de prueba',
  company_description: 'Descripción',
  business_need: 'Necesidad',
  expected_objective: 'Objetivo',
  business_rules: [],
  constraints: [],
  success_criteria: ['Criterio'],
  owner_id: 'owner-1',
  organization_id: null,
  status: 'draft',
  current_phase: 'business_understanding',
  created_at: '2026-10-26T10:00:00Z',
  updated_at: '2026-10-26T10:00:00Z',
};

describe('ProjectLifecycleModal', () => {
  it('requires a reason and submits an archive confirmation', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(
      <ProjectLifecycleModal
        isOpen
        action="archive"
        project={project}
        isSubmitting={false}
        errorMessage={null}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />
    );

    await user.type(screen.getByLabelText(/Motivo/i), 'Cierre de prueba');
    await user.click(screen.getByRole('button', { name: /Archivar proyecto/i }));

    expect(onSubmit).toHaveBeenCalledWith({ actor_id: 'owner-1', reason: 'Cierre de prueba' });
  });
});
