import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StringListInput } from './StringListInput';

describe('StringListInput Component', () => {
  it('renders label and empty state correctly', () => {
    const handleChange = vi.fn();
    render(
      <StringListInput
        id="test-input"
        label="Criterios de Éxito"
        items={[]}
        onChange={handleChange}
        required
        minItems={1}
      />
    );

    expect(screen.getByText(/Criterios de Éxito/)).toBeInTheDocument();
    expect(screen.getByText(/0 elementos/)).toBeInTheDocument();
    expect(screen.getByText(/Debes agregar al menos 1 criterio/)).toBeInTheDocument();
  });

  it('adds an item when typing and clicking Añadir', async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    render(
      <StringListInput
        id="test-input"
        label="Criterios"
        items={['Criterio 1']}
        onChange={handleChange}
      />
    );

    const input = screen.getByRole('textbox');
    await user.type(input, 'Criterio 2');

    const addButton = screen.getByRole('button', { name: /Añadir a Criterios/i });
    await user.click(addButton);

    expect(handleChange).toHaveBeenCalledWith(['Criterio 1', 'Criterio 2']);
  });

  it('adds an item on Enter key press', async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    render(
      <StringListInput
        id="test-input"
        label="Criterios"
        items={[]}
        onChange={handleChange}
      />
    );

    const input = screen.getByRole('textbox');
    await user.type(input, 'Nuevo Criterio{enter}');

    expect(handleChange).toHaveBeenCalledWith(['Nuevo Criterio']);
  });

  it('rejects adding empty or whitespace items', async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    render(
      <StringListInput
        id="test-input"
        label="Criterios"
        items={[]}
        onChange={handleChange}
      />
    );

    const input = screen.getByRole('textbox');
    await user.type(input, '   ');

    const addButton = screen.getByRole('button', { name: /Añadir a Criterios/i });
    await user.click(addButton);

    expect(handleChange).not.toHaveBeenCalled();
    expect(screen.getByText(/El elemento no puede estar vacío/i)).toBeInTheDocument();
  });

  it('removes an item when clicking the remove button', async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    render(
      <StringListInput
        id="test-input"
        label="Criterios"
        items={['Elemento A', 'Elemento B']}
        onChange={handleChange}
      />
    );

    const removeButton = screen.getByRole('button', { name: /Eliminar elemento 1/i });
    await user.click(removeButton);

    expect(handleChange).toHaveBeenCalledWith(['Elemento B']);
  });
});
