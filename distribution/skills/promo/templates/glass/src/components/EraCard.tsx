import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { GlassBG } from './GlassBG';
import { COLORS } from '../constants';

const { fontFamily: poppins } = loadPoppins();

// ACQ-branded chapter / era card. Doubles as the transition between footage sections:
// snaps in over a quick wipe, holds ~2s, snaps to the next section. year + milestone + chapter index.
export const EraCard: React.FC<{ year: string; title: string; chapter: string; sub?: string }> = ({
  year, title, chapter, sub,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const inS = spring({ frame, fps, config: { damping: 200, stiffness: 120, mass: 0.5 } });
  const ruleS = spring({ frame: frame - 6, fps, config: { damping: 200, stiffness: 110, mass: 0.6 } });
  const titleS = spring({ frame: frame - 10, fps, config: { damping: 200, stiffness: 130, mass: 0.5 } });
  const out = interpolate(frame, [durationInFrames - 9, durationInFrames], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const op = Math.min(inS, out);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.sambucus }}>
      <GlassBG />
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: op }}>
        <div style={{ textAlign: 'center', transform: `translateY(${interpolate(inS, [0, 1], [22, 0])}px)` }}>
          <Img src={staticFile('acq-mark-white.png')} style={{ height: 52, opacity: 0.9, marginBottom: 30, filter: `drop-shadow(0 0 18px ${COLORS.indigo}66)` }} />
          <div style={{ fontFamily: poppins, fontWeight: 700, fontSize: 22, letterSpacing: 9, color: COLORS.lavender, marginBottom: 22 }}>{chapter}</div>
          <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 116, lineHeight: 1, color: COLORS.indigo, textShadow: `0 0 46px ${COLORS.indigo}88`, letterSpacing: '-2px' }}>{year}</div>
          <div style={{ width: interpolate(ruleS, [0, 1], [0, 380]), maxWidth: '70vw', height: 3, margin: '28px auto', background: `linear-gradient(90deg, transparent, ${COLORS.indigo}, ${COLORS.lavender}, transparent)` }} />
          <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 70, color: COLORS.white, letterSpacing: '-1.5px', opacity: titleS, transform: `translateY(${interpolate(titleS, [0, 1], [14, 0])}px)` }}>{title}</div>
          {sub && <div style={{ fontFamily: poppins, fontWeight: 400, fontSize: 27, color: 'rgba(255,255,255,0.72)', marginTop: 18, opacity: titleS }}>{sub}</div>}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
