import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { COLORS } from '../constants';
import { CLIPS } from '../data/clips';

const { fontFamily: poppins } = loadPoppins();

// Real finished shorts playing in a grid — header sits in its OWN band above the grid (no overlap).
export const RealClipShowcase: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const COLS = 5, cellW = 182, cellH = 323, gap = 18;
  const labelS = spring({ frame: frame - 2, fps, config: { damping: 200, stiffness: 130, mass: 0.5 } });

  return (
    <AbsoluteFill style={{ backgroundColor: 'transparent', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-start', paddingTop: 44 }}>
      {/* header band (clear of the grid) */}
      <div style={{ height: 122, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: labelS, transform: `translateY(${interpolate(labelS, [0, 1], [-14, 0])}px)` }}>
        <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 56, color: COLORS.white, letterSpacing: '-1px' }}>
          10 shorts. <span style={{ color: COLORS.indigo }}>From one Q&A.</span>
        </div>
        <div style={{ fontFamily: poppins, fontWeight: 600, fontSize: 19, color: COLORS.lavender, letterSpacing: '3px', textTransform: 'uppercase', marginTop: 8 }}>
          Instagram · TikTok · YouTube Shorts
        </div>
      </div>

      {/* grid */}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${COLS}, ${cellW}px)`, gap, marginTop: 14 }}>
        {CLIPS.map((id, i) => {
          const s = spring({ frame: frame - 10 - i * 4, fps, config: { damping: 200, stiffness: 150, mass: 0.4 } });
          return (
            <div key={id} style={{
              width: cellW, height: cellH, borderRadius: 12, overflow: 'hidden',
              opacity: s, transform: `scale(${interpolate(s, [0, 1], [0.55, 1])}) translateY(${interpolate(s, [0, 1], [28, 0])}px)`,
              border: '1px solid rgba(111,0,255,0.35)', boxShadow: '0 16px 40px rgba(0,0,0,0.55)', background: '#000',
            }}>
              <OffthreadVideo src={staticFile(`clips/${id}.mp4`)} startFrom={30 + i * 12} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
