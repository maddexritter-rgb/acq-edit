import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';

// Persistent liquid-glass backdrop: deep gradient + slowly drifting color orbs.
// Place as the BASE layer of a composition (outside all sequences) so it never cuts —
// every beat shares the same living background, which is what makes the video feel continuous.
const ORBS = [
  { c: '#6f00ff', x: 24, y: 28, r: 1000, sp: 0.0042, ph: 0, amp: 90 },
  { c: '#2d64e3', x: 78, y: 66, r: 1100, sp: 0.0032, ph: 2.1, amp: 110 },
  { c: '#a08bec', x: 62, y: 18, r: 760, sp: 0.0051, ph: 4.0, amp: 76 },
  { c: '#6f00ff', x: 14, y: 82, r: 880, sp: 0.0036, ph: 1.2, amp: 100 },
];

export const GlassBG: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: 'radial-gradient(ellipse at 50% 38%, #171c38 0%, #0b0c18 78%)', overflow: 'hidden' }}>
      {ORBS.map((o, i) => {
        const dx = Math.sin(frame * o.sp + o.ph) * o.amp;
        const dy = Math.cos(frame * o.sp * 0.8 + o.ph) * o.amp;
        return (
          <div key={i} style={{
            position: 'absolute', left: `${o.x}%`, top: `${o.y}%`, width: o.r, height: o.r,
            transform: `translate(-50%,-50%) translate(${dx}px, ${dy}px)`,
            borderRadius: '50%',
            background: `radial-gradient(circle, ${o.c}4d 0%, transparent 70%)`,
            filter: 'blur(45px)',
          }} />
        );
      })}
      {/* fine top sheen + vignette for depth */}
      <AbsoluteFill style={{ background: 'linear-gradient(180deg, rgba(255,255,255,0.04) 0%, transparent 18%)' }} />
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, transparent 52%, rgba(0,0,0,0.5) 100%)' }} />
    </AbsoluteFill>
  );
};
