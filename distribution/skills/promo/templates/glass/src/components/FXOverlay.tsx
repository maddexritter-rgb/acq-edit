import React from 'react';
import { AbsoluteFill } from 'remotion';

// Cinematic finishing layer: vignette + subtle film grain.
// Grain is rendered at low resolution (fixed seed) and stretched, so it stays cheap to render.
// Drop at the TOP of a composition (renders above everything) for an instant "graded" feel.
export const FXOverlay: React.FC<{ grain?: number; vignette?: number }> = ({ grain = 0.045, vignette = 0.5 }) => {
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <AbsoluteFill style={{
        background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 52%, rgba(0,0,0,${vignette}) 100%)`,
      }} />
      <svg width={480} height={270} preserveAspectRatio="none"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: grain, mixBlendMode: 'overlay' }}>
        <filter id="acqgrain">
          <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" seed={7} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#acqgrain)" />
      </svg>
    </AbsoluteFill>
  );
};
