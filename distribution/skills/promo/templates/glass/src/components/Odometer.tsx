import React from 'react';
import { useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';

const { fontFamily: poppins } = loadPoppins();

// Count-up number. Animates 0 → target over `dur` frames starting at `delay`.
// `format` maps the live numeric value to a display string.
export const Odometer: React.FC<{
  target: number;
  delay?: number;
  dur?: number;
  format?: (n: number) => string;
  style?: React.CSSProperties;
}> = ({ target, delay = 0, dur = 40, format, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, durationInFrames: dur, config: { damping: 200, stiffness: 80, mass: 0.8 } });
  const val = interpolate(s, [0, 1], [0, target]);
  const display = format ? format(val) : Math.round(val).toLocaleString();
  return (
    <span style={{ fontFamily: poppins, fontWeight: 800, fontVariantNumeric: 'tabular-nums', ...style }}>
      {display}
    </span>
  );
};

// Helpers for big-number formatting
export const fmtBillions = (n: number) => `${(n / 1e9).toFixed(1)}B`;
export const fmtCommas = (n: number) => Math.round(n).toLocaleString();
