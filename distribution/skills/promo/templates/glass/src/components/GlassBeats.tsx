import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { COLORS } from '../constants';
import { GlassPanel } from './GlassPanel';
import { NarratorChip } from './CreateShots';

const { fontFamily: poppins } = loadPoppins();
const SNAPPY = { damping: 200, stiffness: 130, mass: 0.5 };

// A scene shown inside a glass frame with a plain-English narration line under it.
export const SceneDemo: React.FC<{ label: string; caption: string; captionAt?: number; children: React.ReactNode }> = ({ label, caption, captionAt = 8, children }) => (
  <AbsoluteFill>
    <GlassFrame label={label}>{children}</GlassFrame>
    <NarratorChip caption={caption} at={captionAt} />
  </AbsoluteFill>
);

// A clean punch-in "payoff" angle: one big result on a dark glass card + narration.
export const PayoffCard: React.FC<{ big: string; sub: string; caption: string; accent?: boolean }> = ({ big, sub, caption, accent }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 110, mass: 0.6 } });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <GlassPanel dark radius={26} style={{ padding: '58px 88px', textAlign: 'center', opacity: s, transform: `scale(${interpolate(s, [0, 1], [0.92, 1])})`, marginBottom: 40 }}>
        <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 116, lineHeight: 1, letterSpacing: '-3px', color: accent ? COLORS.lavender : COLORS.white, textShadow: '0 0 50px rgba(111,0,255,0.4)' }}>{big}</div>
        <div style={{ fontFamily: poppins, fontWeight: 300, fontSize: 32, color: 'rgba(255,255,255,0.72)', marginTop: 14 }}>{sub}</div>
      </GlassPanel>
      <NarratorChip caption={caption} />
    </AbsoluteFill>
  );
};

// Reusable liquid-glass beats so every video shares one language.

export const GlassTitle: React.FC<{ line1: string; indigoWord: string; sub?: string }> = ({ line1, indigoWord, sub }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 120, mass: 0.6 } });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <GlassPanel radius={28} style={{ padding: '52px 78px', maxWidth: 1560, opacity: s, transform: `scale(${interpolate(s, [0, 1], [0.93, 1])})` }}>
        <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 96, lineHeight: 1.03, letterSpacing: '-2px', color: '#fff', textAlign: 'center' }}>
          {line1}<span style={{ color: COLORS.indigo }}>{indigoWord}.</span>
        </div>
        {sub && <div style={{ fontFamily: poppins, fontWeight: 300, fontSize: 30, color: 'rgba(255,255,255,0.72)', textAlign: 'center', marginTop: 16 }}>{sub}</div>}
      </GlassPanel>
    </AbsoluteFill>
  );
};

export const GlassFrame: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 110, mass: 0.6 } });
  return (
    <AbsoluteFill style={{ padding: '74px 96px', opacity: s, transform: `scale(${interpolate(s, [0, 1], [0.97, 1])})` }}>
      <GlassPanel dark radius={18} sheen={false} style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0 }}>
        <div style={{ height: 50, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10, padding: '0 18px', borderBottom: '1px solid rgba(255,255,255,0.10)', background: 'rgba(255,255,255,0.04)' }}>
          {['#ff5f56', '#ffbd2e', '#27c93f'].map((c) => <div key={c} style={{ width: 12, height: 12, borderRadius: '50%', background: c, opacity: 0.85 }} />)}
          <div style={{ marginLeft: 14, fontFamily: poppins, fontSize: 12, fontWeight: 600, letterSpacing: '3px', textTransform: 'uppercase', color: 'rgba(160,139,236,0.7)' }}>{label}</div>
        </div>
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>{children}</div>
      </GlassPanel>
    </AbsoluteFill>
  );
};

export const GlassOutro: React.FC<{ metric: string; sub: string; tagline?: string }> = ({ metric, sub, tagline }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const m = spring({ frame: f, fps, config: SNAPPY });
  const logo = spring({ frame: f - 12, fps, config: SNAPPY });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
      {/* scrim BEHIND the text (zIndex 0) — covers the previous beat + the drifting BG orbs so the glow stays CONSTANT, but does NOT dim the text (which sits in the zIndex-1 layer) */}
      <AbsoluteFill style={{ background: 'rgba(9,10,20,0.8)', zIndex: 0 }} />
      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 104, color: '#fff', letterSpacing: '-3px', textAlign: 'center', opacity: m, transform: `translateY(${interpolate(m, [0, 1], [30, 0])}px)`, textShadow: '0 0 44px rgba(111,0,255,0.55)' }}>{metric}</div>
        <div style={{ fontFamily: poppins, fontWeight: 500, fontSize: 40, color: '#ffffff', marginTop: 12, textAlign: 'center', opacity: m, textShadow: '0 0 22px rgba(124,77,255,0.95)' }}>{sub}</div>
        {tagline && <div style={{ fontFamily: poppins, fontWeight: 700, fontSize: 26, color: '#d9ccfa', letterSpacing: '3px', textTransform: 'uppercase', marginTop: 22, opacity: m, textShadow: '0 0 20px rgba(124,77,255,1)' }}>{tagline}</div>}
        <Img src={staticFile('acq-logo-trim.png')} style={{ width: 600, height: 'auto', marginTop: 46, opacity: logo, transform: `translateY(${interpolate(logo, [0, 1], [16, 0])}px)` }} />
      </div>
    </AbsoluteFill>
  );
};
