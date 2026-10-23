import React from 'react';
import {
  AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig, Easing,
} from 'remotion';
import {CTAPill} from './CTAPill';

// Palette from references/ad_style_spec.md + acquisition.com/fivescalingframeworks (measured live).
const PURPLE_TOP = '#A86EFF';
const PURPLE_BOTTOM = '#7E30FE';
const DEEP = '#4600A9';
const INK = '#0A0C16';
const GOLD = '#E8AE2B';
const WHITE = '#F7F7FD';

export const W = 1080;
export const H = 1920;

const FRAMEWORKS = [
  'Lead Generation',
  'Sales Conversion',
  'Retention & Proof',
  'Product',
  'Onboarding & Offboarding',
];

const F = 'Inter, -apple-system, Helvetica, Arial, sans-serif';

export const SopFrameworksEndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const reveal = (delaySec: number, dur = 0.4) =>
    interpolate(frame, [fps * delaySec, fps * (delaySec + dur)], [0, 1], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    });

  const badge = reveal(0.05);
  const h1 = reveal(0.25);
  const h2 = reveal(0.42);
  const sub = reveal(0.65);
  const pillListDelay = 0.95;

  return (
    <AbsoluteFill style={{fontFamily: F}}>
      {/* background */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(120% 70% at 50% 26%, ${DEEP} 0%, ${INK} 78%)`,
        }}
      />
      {/* faint brand watermark, top-right, clear of the right action column */}
      <div style={{
        position: 'absolute', top: 64, right: 56, display: 'flex', alignItems: 'center', gap: 8,
        opacity: 0.55,
      }}>
        <div style={{
          width: 22, height: 22, borderRadius: 6, background: 'rgba(255,255,255,0.12)',
          border: '1px solid rgba(255,255,255,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{color: WHITE, fontSize: 12}}>✓</span>
        </div>
        <span style={{color: WHITE, fontWeight: 700, fontSize: 20, letterSpacing: 0.5}}>acquisition.com</span>
      </div>

      {/* qualifier badge */}
      <div style={{
        position: 'absolute', top: 210, left: 60,
        opacity: badge, transform: `translateY(${interpolate(badge, [0, 1], [16, 0])}px)`,
      }}>
        <div style={{
          background: GOLD, color: INK, fontWeight: 800, fontSize: 26, letterSpacing: 0.5,
          padding: '10px 22px', borderRadius: 999, display: 'inline-block',
        }}>
          BEST FOR $1M+ OWNERS
        </div>
      </div>

      {/* headline */}
      <div style={{position: 'absolute', top: 300, left: 60, right: 60}}>
        <div style={{
          color: WHITE, fontWeight: 900, fontSize: 96, lineHeight: 0.98, letterSpacing: -1,
          opacity: h1, transform: `translateY(${interpolate(h1, [0, 1], [24, 0])}px)`,
          textShadow: '0 4px 30px rgba(255,255,255,0.15)',
        }}>
          5 SCALING
        </div>
        <div style={{
          fontWeight: 900, fontSize: 96, lineHeight: 0.98, letterSpacing: -1,
          background: `linear-gradient(180deg, ${PURPLE_TOP}, ${PURPLE_BOTTOM})`,
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          opacity: h2, transform: `translateY(${interpolate(h2, [0, 1], [24, 0])}px)`,
          filter: 'drop-shadow(0 4px 30px rgba(126,48,254,0.45))',
        }}>
          FRAMEWORKS
        </div>
        <div style={{
          marginTop: 18, color: 'rgba(247,247,253,0.72)', fontWeight: 500, fontSize: 30,
          opacity: sub, transform: `translateY(${interpolate(sub, [0, 1], [14, 0])}px)`,
          maxWidth: 780,
        }}>
          What we actually use across our $250M+ portfolio — yours free.
        </div>
      </div>

      {/* the 5 frameworks, staggered */}
      <div style={{position: 'absolute', top: 740, left: 60, right: 60, display: 'flex', flexDirection: 'column', gap: 20}}>
        {FRAMEWORKS.map((label, i) => {
          const r = reveal(pillListDelay + i * 0.16, 0.5);
          return (
            <div key={label} style={{
              display: 'flex', alignItems: 'center', gap: 22,
              opacity: r, transform: `translateX(${interpolate(r, [0, 1], [-36, 0])}px)`,
            }}>
              <div style={{
                width: 62, height: 62, borderRadius: 18, flexShrink: 0,
                background: 'rgba(255,255,255,0.08)', border: '1.5px solid rgba(255,255,255,0.18)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{color: GOLD, fontWeight: 800, fontSize: 26}}>
                  {String(i + 1).padStart(2, '0')}
                </span>
              </div>
              <span style={{color: WHITE, fontWeight: 700, fontSize: 40}}>{label}</span>
            </div>
          );
        })}
      </div>

      {/* CTA pill — same house component. Bottom must clear y=1500 (platform UI safe zone).
          Sequence-offset so its own spring-in fires after the list finishes, not at frame 0. */}
      <Sequence from={Math.round(fps * 2.7)}>
        <div style={{position: 'absolute', top: 1260, left: 0, width: W, height: 200}}>
          <CTAPill line1="5 FREE SCALING FRAMEWORKS" line2="CLICK THE LINK BELOW" />
        </div>
      </Sequence>
    </AbsoluteFill>
  );
};
