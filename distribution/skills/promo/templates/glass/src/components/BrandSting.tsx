import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { COLORS } from '../constants';

const rand = (n: number) => { const x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); };

// ~1.5s punchy logo sting: streaks converge → flash → big mark blooms in → wordmark.
export const BrandSting: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const cx = width / 2, cy = height / 2;
  const converge = interpolate(frame, [0, 13], [1, 0], { extrapolateRight: 'clamp', easing: (t) => t * t });
  const flash = interpolate(frame, [11, 15, 24], [0, 0.85, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const markS = spring({ frame: frame - 12, fps, config: { damping: 200, stiffness: 150, mass: 0.5 } });
  const wordS = spring({ frame: frame - 22, fps, config: { damping: 200, stiffness: 150, mass: 0.5 } });
  const settle = interpolate(frame, [12, 44], [1.12, 1], { extrapolateRight: 'clamp' });
  // fade the logo out at the very end so it doesn't bleed THROUGH the next (translucent glass) card during the crossfade
  const exit = interpolate(frame, [37, 45], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ backgroundColor: '#05060d', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
      {Array.from({ length: 44 }).map((_, i) => {
        const ang = rand(i) * Math.PI * 2;
        const dist = (320 + rand(i + 7) * 760) * converge;
        const x = cx + Math.cos(ang) * dist;
        const y = cy + Math.sin(ang) * dist;
        const len = 40 + rand(i + 3) * 110;
        return (
          <div key={i} style={{
            position: 'absolute', left: x, top: y, width: len, height: 2.5,
            background: `linear-gradient(90deg, transparent, ${i % 3 === 0 ? COLORS.lavender : COLORS.indigo})`,
            transform: `rotate(${ang + Math.PI}rad)`,
            opacity: interpolate(converge, [0, 1], [1, 0]) * 0.9, filter: 'blur(0.5px)',
          }} />
        );
      })}

      <div style={{
        position: 'absolute', width: 820, height: 820, borderRadius: '50%',
        background: `radial-gradient(circle, rgba(111,0,255,${0.3 * markS}) 0%, transparent 62%)`,
        opacity: exit,
      }} />

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 30, transform: `scale(${settle})`, opacity: exit }}>
        <Img src={staticFile('acq-mark-trim.png')} style={{
          height: 250, objectFit: 'contain',
          opacity: markS, transform: `scale(${interpolate(markS, [0, 1], [0.4, 1])})`,
          filter: `drop-shadow(0 0 ${44 * markS}px rgba(111,0,255,0.8))`,
        }} />
        <div style={{ overflow: 'hidden', height: 64 }}>
          <Img src={staticFile('acq-logo-trim.png')} style={{
            width: 560, height: 'auto', objectFit: 'contain',
            opacity: wordS, transform: `translateY(${interpolate(wordS, [0, 1], [64, 0])}px)`,
          }} />
        </div>
      </div>

      <AbsoluteFill style={{ background: '#ffffff', opacity: flash }} />
    </AbsoluteFill>
  );
};
