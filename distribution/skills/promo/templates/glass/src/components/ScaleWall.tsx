import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { COLORS } from '../constants';
import { Odometer, fmtCommas } from './Odometer';

const { fontFamily: poppins } = loadPoppins();
const rand = (n: number) => { const x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); };

const PAIRS = [['#6f00ff', '#a08bec'], ['#2d64e3', '#6f00ff'], ['#a08bec', '#6f00ff'], ['#5a00d6', '#2d64e3'], ['#7a1fff', '#a08bec']];

// A wall of clip cards that rapidly multiplies, with a big count-up overlay.
// Use for scale "oh shit" — e.g. target 29,166 (the real archive) or 400 (/mo).
export const ScaleWall: React.FC<{ cols?: number; rows?: number; target: number; label: string }> = ({
  cols = 16, rows = 9, target, label,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const cw = width / cols, ch = height / rows;
  const total = cols * rows;

  const labelS = spring({ frame: frame - 30, fps, config: { damping: 200, stiffness: 90, mass: 0.7 } });

  return (
    <AbsoluteFill style={{ backgroundColor: 'transparent', overflow: 'hidden' }}>
      {Array.from({ length: total }).map((_, i) => {
        // fill order: spiral-ish via shuffled index by hash
        const order = rand(i) * total;
        const appear = Math.floor(order * 0.9);
        const s = spring({ frame: frame - appear, fps, config: { damping: 200, stiffness: 160, mass: 0.4 } });
        if (frame < appear) return null;
        const c = i % cols, r = Math.floor(i / cols);
        const [a, b] = PAIRS[i % PAIRS.length];
        return (
          <div key={i} style={{
            position: 'absolute', left: c * cw + 4, top: r * ch + 4, width: cw - 8, height: ch - 8,
            borderRadius: 6, background: `linear-gradient(150deg, ${a}, ${b})`,
            opacity: s * 0.92, transform: `scale(${interpolate(s, [0, 1], [0.4, 1])})`,
            border: '1px solid rgba(255,255,255,0.08)',
          }} />
        );
      })}

      {/* darken + count overlay */}
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, rgba(7,8,15,0.78) 0%, rgba(7,8,15,0.55) 100%)' }} />
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
        <Odometer target={target} delay={30} dur={50} format={fmtCommas}
          style={{ fontSize: 200, color: COLORS.white, lineHeight: 1, letterSpacing: '-6px', textShadow: '0 0 60px rgba(111,0,255,0.5)' }} />
        <div style={{
          fontFamily: poppins, fontWeight: 600, fontSize: 34, color: COLORS.lavender, letterSpacing: '4px',
          textTransform: 'uppercase', marginTop: 16, opacity: labelS,
        }}>{label}</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
