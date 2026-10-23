import React from 'react';
import { useCurrentFrame, useVideoConfig } from 'remotion';
import { loadFont as loadMono } from '@remotion/google-fonts/JetBrainsMono';
import { COLORS } from '../constants';

const { fontFamily: mono } = loadMono();

// Live stopwatch that runs from `startFrame`, freezes at `freezeFrame`.
// Displays S.cc (seconds.centiseconds). Turns green when frozen.
export const Stopwatch: React.FC<{
  startFrame: number;
  freezeFrame: number;
  size?: number;
  label?: string;
}> = ({ startFrame, freezeFrame, size = 40, label = 'HUMAN TIME' }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const live = Math.max(0, Math.min(frame, freezeFrame) - startFrame);
  const secs = live / fps;
  const frozen = frame >= freezeFrame;
  const txt = secs.toFixed(2).padStart(5, '0');

  if (frame < startFrame) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
      <span style={{ fontFamily: mono, fontSize: size * 0.3, letterSpacing: '3px', color: 'rgba(160,139,236,0.7)', textTransform: 'uppercase' }}>
        {label}
      </span>
      <span style={{
        fontFamily: mono, fontWeight: 700, fontSize: size,
        color: frozen ? '#27c93f' : COLORS.white,
        textShadow: frozen ? '0 0 24px rgba(39,201,63,0.6)' : '0 0 18px rgba(111,0,255,0.35)',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {txt}s
      </span>
    </div>
  );
};
