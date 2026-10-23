import React from 'react';
import {
  AbsoluteFill, Img, staticFile, interpolate, spring,
  useCurrentFrame, useVideoConfig, Easing,
} from 'remotion';

const GOLD = '#E8AE2B';
const BORDER = 'rgba(196,170,255,0.62)';

export const PILL_W = 1000;
export const PILL_H = 142;
export const PAD = 70;                       // room for the glow

export const CTAPill: React.FC<{line1?: string; line2?: string}> = ({
  line1 = 'GET THE FREE CONSTRAINT FINDER',
  line2 = 'CLICK THE LINK BELOW',
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const enter = spring({frame, fps, config: {damping: 200, stiffness: 130, mass: 0.55}});
  const y = interpolate(enter, [0, 1], [220, 0]);
  const op = interpolate(frame, [0, 5], [0, 1], {extrapolateRight: 'clamp'});

  // shine sweep, once, shortly after it lands
  const g = interpolate(frame, [fps * 0.5, fps * 1.5], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad),
  });

  // slow breathing glow so it stays alive on screen
  const pulse = 0.82 + 0.18 * Math.sin((frame / fps) * 2.1);

  const F = 'Inter, -apple-system, Helvetica, Arial, sans-serif';

  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      <div style={{
        width: PILL_W, height: PILL_H, transform: `translateY(${y}px)`, opacity: op,
        position: 'relative', fontFamily: F,
      }}>
        {/* outer glow */}
        <div style={{
          position: 'absolute', inset: -12, borderRadius: PILL_H,
          background: 'radial-gradient(closest-side, rgba(138,61,255,0.85), rgba(138,61,255,0))',
          filter: 'blur(26px)', opacity: pulse,
        }} />

        {/* body */}
        <div style={{
          position: 'absolute', inset: 0, borderRadius: PILL_H / 2, overflow: 'hidden',
          background: 'linear-gradient(135deg, #8B37FF 0%, #6A18DC 46%, #4A0FA8 100%)',
          border: `2px solid ${BORDER}`,
          boxShadow: 'inset 0 2px 0 rgba(255,255,255,0.30), 0 18px 40px rgba(30,0,80,0.55)',
          display: 'flex', alignItems: 'center', paddingLeft: 30, gap: 22,
        }}>
          {/* glass sheen across the top half */}
          <div style={{
            position: 'absolute', left: 0, right: 0, top: 0, height: '54%',
            background: 'linear-gradient(180deg, rgba(255,255,255,0.26), rgba(255,255,255,0))',
            pointerEvents: 'none',
          }} />

          {/* travelling shine */}
          <div style={{
            position: 'absolute', top: '-60%', bottom: '-60%', width: 190,
            left: `${interpolate(g, [0, 1], [-25, 115])}%`,
            background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.42), transparent)',
            transform: 'skewX(-18deg)', pointerEvents: 'none',
          }} />

          {/* brand mark — sized so the thin outline actually reads */}
          <div style={{
            width: 82, height: 82, borderRadius: 41, flexShrink: 0,
            background: 'rgba(255,255,255,0.14)',
            border: '2px solid rgba(255,255,255,0.30)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Img src={staticFile('acq-mark-white.png')}
                 style={{width: 54, height: 54, objectFit: 'contain'}} />
          </div>

          <div style={{display: 'flex', flexDirection: 'column', gap: 2, zIndex: 2}}>
            <span style={{
              color: GOLD, fontWeight: 900, fontSize: 40, letterSpacing: 0.2, whiteSpace: 'nowrap',
              textShadow: '0 2px 10px rgba(0,0,0,0.35)',
            }}>{line1}</span>
            <span style={{
              color: '#fff', fontWeight: 800, fontSize: 34, letterSpacing: 0.5, whiteSpace: 'nowrap',
              textShadow: '0 2px 8px rgba(0,0,0,0.35)',
            }}>{line2}</span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
