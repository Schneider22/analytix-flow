import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import * as healthApi from './api/health';
import { ApiError, NetworkError } from './api/client';

describe('App Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders initial screen with title, branding and architectural cards', async () => {
    vi.spyOn(healthApi, 'getHealth').mockResolvedValueOnce({
      status: 'ok',
      database: 'ok',
    });

    render(<App />);

    expect(screen.getByText('AnalytixFlow')).toBeInTheDocument();
    expect(screen.getByText('Business Portal')).toBeInTheDocument();
    expect(screen.getByText('Portal de Negocio y Gobernanza Analítica')).toBeInTheDocument();
    expect(screen.getByText('Gobernanza Humana')).toBeInTheDocument();
    expect(screen.getByText('Linaje Criptográfico')).toBeInTheDocument();
    expect(screen.getByText('Cero Fabricación')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Disponible');
    });
  });

  it('displays "Disponible" with health data when backend health succeeds', async () => {
    vi.spyOn(healthApi, 'getHealth').mockResolvedValueOnce({
      status: 'ok',
      database: 'ok',
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Disponible');
    });

    expect(screen.getByText('Servicio API')).toBeInTheDocument();
    expect(screen.getAllByText('Base de Datos').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('icon-available')).toBeInTheDocument();
  });

  it('displays "No disponible" and error message when network request fails', async () => {
    vi.spyOn(healthApi, 'getHealth').mockRejectedValueOnce(
      new NetworkError(new Error('Connection refused'))
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('No disponible');
    });

    expect(screen.getByText('No se pudo comunicar con el backend')).toBeInTheDocument();
    expect(screen.getByText(/Connection refused/)).toBeInTheDocument();
    expect(screen.getByTestId('icon-unavailable')).toBeInTheDocument();
  });

  it('displays "No disponible" when backend returns HTTP 503 or 500 error', async () => {
    vi.spyOn(healthApi, 'getHealth').mockRejectedValueOnce(
      new ApiError(503, 'Persistence service unavailable')
    );

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('No disponible');
    });

    expect(screen.getByText(/Persistence service unavailable/)).toBeInTheDocument();
  });

  it('retries health check when clicking the "Reintentar comprobación" button', async () => {
    const user = userEvent.setup();
    const healthSpy = vi
      .spyOn(healthApi, 'getHealth')
      .mockRejectedValueOnce(new NetworkError(new Error('Network failure')))
      .mockResolvedValueOnce({
        status: 'ok',
        database: 'ok',
      });

    render(<App />);

    // Initially fails
    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('No disponible');
    });

    // Click retry
    const retryButton = screen.getByRole('button', { name: /Reintentar comprobación/i });
    await user.click(retryButton);

    // Transitions to available on second attempt
    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Disponible');
    });

    expect(healthSpy).toHaveBeenCalledTimes(2);
  });
});
