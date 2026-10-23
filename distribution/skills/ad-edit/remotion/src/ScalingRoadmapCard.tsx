import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from 'remotion';

// Palette from references/ad_style_spec.md (measured off shipped ads).
// Content grounded in the actual product page (acquisition.com/roadmap): "Get Your Free
// Personalized $100M Scaling Roadmap...in under 30 seconds." — same numbers, same claim.
const PURPLE = '#6D20E0';
const DEEP = '#4600A9';
const INK = '#0A0C16';
const HEADER = '#131521';

export const CARD_W = 820;
export const CARD_H = 640;
export const TARGET = 100;

const Ring: React.FC<{progress: number}> = ({progress}) => {
  const R = 92;
  const STROKE = 20;
  const C = 2 * Math.PI * R;
  return (
    <svg width={R * 2 + STROKE * 2} height={R * 2 + STROKE * 2}>
      <circle
        cx={R + STROKE} cy={R + STROKE} r={R}
        stroke="#E9E9F0" strokeWidth={STROKE} fill="none"
      />
      <circle
        cx={R + STROKE} cy={R + STROKE} r={R}
        stroke={PURPLE} strokeWidth={STROKE} fill="none" strokeLinecap="round"
        strokeDasharray={C}
        strokeDashoffset={C * (1 - progress)}
        transform={`rotate(-90 ${R + STROKE} ${R + STROKE})`}
      />
    </svg>
  );
};

export const ScalingRoadmapCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  const inS = spring({frame, fps, config: {damping: 200, stiffness: 110, mass: 0.6}});
  const outStart = durationInFrames - Math.round(fps * 0.45);
  const outP = interpolate(frame, [outStart, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic),
  });
  const scale = interpolate(inS, [0, 1], [0.9, 1]) * interpolate(outP, [0, 1], [0.97, 1]);
  const opacity = Math.min(inS, outP);

  const sweep = interpolate(frame, [Math.round(fps * 0.35), Math.round(fps * 1.7)], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const shown = Math.round(TARGET * sweep);

  const reveal = (delaySec: number) =>
    interpolate(frame, [fps * delaySec, fps * (delaySec + 0.35)], [0, 1], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    });

  const label = reveal(1.35);
  const answer = reveal(1.6);
  const bar1 = reveal(1.95);
  const bar2 = reveal(2.1);
  const pill = reveal(2.35);

  const F = 'Inter, -apple-system, Helvetica, Arial, sans-serif';

  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', background: 'transparent'}}>
      <div
        style={{
          width: CARD_W, height: CARD_H, borderRadius: 34, overflow: 'hidden',
          background: '#fff', transform: `scale(${scale})`, opacity,
          boxShadow: '0 26px 70px rgba(0,0,0,0.55)', fontFamily: F,
        }}
      >
        <div style={{
          height: 92, background: HEADER, display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', padding: '0 34px',
        }}>
          <span style={{color: '#fff', fontWeight: 800, fontSize: 24, letterSpacing: 1.5}}>
            SCALING ROADMAP
          </span>
          <span style={{color: 'rgba(255,255,255,0.72)', fontWeight: 700, fontSize: 22, letterSpacing: 1.5}}>
            ACQUISITION.COM
          </span>
        </div>

        <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 26}}>
          <div style={{position: 'relative'}}>
            <Ring progress={sweep} />
            <div style={{
              position: 'absolute', inset: 0, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              fontSize: 58, fontWeight: 900, color: INK,
            }}>
              ${shown}M
            </div>
          </div>

          <div style={{
            marginTop: 20, fontSize: 22, letterSpacing: 2, fontWeight: 700,
            color: '#808496', opacity: label,
            transform: `translateY(${interpolate(label, [0, 1], [10, 0])}px)`,
          }}>
            YOUR FREE
          </div>

          <div style={{
            marginTop: 8, fontSize: 46, fontWeight: 900, color: INK, opacity: answer,
            transform: `translateY(${interpolate(answer, [0, 1], [14, 0])}px)`,
          }}>
            Scaling Roadmap
          </div>

          <div style={{width: CARD_W - 130, marginTop: 30}}>
            {[bar1, bar2].map((o, i) => (
              <div key={i} style={{
                height: 18, borderRadius: 9, background: '#EEEFF5',
                marginBottom: 14, width: `${i === 0 ? 100 : 74}%`,
                opacity: o, transform: `translateX(${interpolate(o, [0, 1], [-16, 0])}px)`,
              }} />
            ))}
          </div>

          <div style={{
            alignSelf: 'flex-start', marginLeft: 65, marginTop: 6,
            background: '#F0EAFE', color: DEEP, fontWeight: 800, fontSize: 21,
            letterSpacing: 1.2, padding: '13px 24px', borderRadius: 24,
            opacity: pill, transform: `scale(${interpolate(pill, [0, 1], [0.94, 1])})`,
          }}>
            TAKES ONLY 30 SECONDS
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
