import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrandLogo } from './BrandLogo';

describe('BrandLogo Component', () => {
  it('renders full brand logo with symbol, name and slogan by default', () => {
    render(<BrandLogo />);

    expect(screen.getByTestId('brand-logo')).toBeInTheDocument();
    expect(screen.getByText('AnalytixFlow')).toBeInTheDocument();
    expect(screen.getByText('AI-Powered Analytics Platform')).toBeInTheDocument();
  });

  it('renders compact variant without slogan', () => {
    render(<BrandLogo variant="compact" />);

    expect(screen.getByTestId('brand-logo')).toBeInTheDocument();
    expect(screen.getByText('AnalytixFlow')).toBeInTheDocument();
    expect(screen.queryByText('AI-Powered Analytics Platform')).not.toBeInTheDocument();
  });

  it('renders symbol-only variant', () => {
    render(<BrandLogo variant="symbol" />);

    expect(screen.getByTestId('brand-logo')).toBeInTheDocument();
    expect(screen.getByLabelText('AnalytixFlow Logo Symbol')).toBeInTheDocument();
    expect(screen.queryByText('AnalytixFlow')).not.toBeInTheDocument();
  });

  it('applies custom size and className correctly', () => {
    render(<BrandLogo size="lg" className="custom-test-class" />);

    const container = screen.getByTestId('brand-logo');
    expect(container).toHaveClass('custom-test-class');
  });
});