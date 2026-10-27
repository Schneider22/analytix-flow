import React from 'react';
import logoImage from '../../assets/analytixflow-logo.png';

const officialLogo = logoImage;
const officialSymbol = '/analytixflow-symbol.png';

export interface BrandLogoProps {
  variant?: 'full' | 'compact' | 'symbol';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  showSlogan?: boolean;
}

/**
 * BrandLogo — Integrates the official AnalytixFlow raster logo.
 *
 * The logo PNG is the authoritative source:
 *   - 3D stylised «A» with turquoise/emerald gradients
 *   - Analytical bar charts inside the symbol
 *   - Flowing data-arc curve and connected nodes
 *   - "AI-POWERED" / "ANALYTICS PLATFORM" text integrated in the asset
 *   - Five gradient bars at the bottom
 *
 * Do NOT replace this with an inline SVG reinterpretation or a generic icon.
 */
export const BrandLogo: React.FC<BrandLogoProps> = ({
  variant = 'full',
  size = 'md',
  className = '',
  showSlogan = true,
}) => {
  const sizeMap = {
    sm: { symbol: 'h-8 w-8', full: 'h-24 w-auto', name: 'text-[17px]', slogan: 'text-[9px]' },
    md: { symbol: 'h-10 w-10', full: 'h-36 w-auto', name: 'text-[19px]', slogan: 'text-[10px]' },
    lg: { symbol: 'h-12 w-12', full: 'h-48 w-auto', name: 'text-[24px]', slogan: 'text-xs' },
  };

  const s = sizeMap[size] ?? sizeMap.md;

  // Symbol-only variant
  if (variant === 'symbol') {
    return (
      <div data-testid="brand-logo" className={`inline-flex items-center ${className}`}>
        <img
          src={officialSymbol}
          alt="AnalytixFlow Logo Symbol"
          aria-label="AnalytixFlow Logo Symbol"
          className={`${s.symbol} object-contain flex-shrink-0`}
          draggable={false}
        />
      </div>
    );
  }

  // Compact is used in navigation: the square crop is derived from the official PNG,
  // while the wordmark remains real text so it stays crisp at small sizes.
  if (variant === 'compact') {
    return (
      <div
        data-testid="brand-logo"
        className={`inline-flex min-w-0 items-center space-x-2.5 select-none ${className}`}
      >
        <img
          src={officialSymbol}
          alt="AnalytixFlow Logo Symbol"
          className={`${s.symbol} object-contain flex-shrink-0`}
          draggable={false}
        />
        <span className={`${s.name} whitespace-nowrap font-bold leading-none text-darktext-primary tracking-tight`}>
          AnalytixFlow
        </span>
      </div>
    );
  }

  return (
    <div
      data-testid="brand-logo"
      className={`inline-flex flex-col items-center select-none ${className}`}
    >
      <img
        src={officialLogo}
        alt="AnalytixFlow official logo"
        className={`${s.full} max-w-full object-contain flex-shrink-0`}
        draggable={false}
      />
      <span className="sr-only">AnalytixFlow</span>
      {showSlogan && <span className="sr-only">AI-Powered Analytics Platform</span>}
    </div>
  );
};
