import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { loadFont as loadMono } from '@remotion/google-fonts/JetBrainsMono';
import { COLORS } from '../constants';
import { TOP_CLIPS, GRAND_TOTAL_VIEWS_FMT, TOTAL_CLIPS } from '../data/receipts';
import { Odometer, fmtCommas } from './Odometer';

const { fontFamily: poppins } = loadPoppins();
const { fontFamily: mono } = loadMono();

const PLAT: Record<string, string> = { Instagram: '#e1306c', YouTube: '#ff0033', TikTok: '#25f4ee', X: '#a08bec', Facebook: '#2d64e3' };

// Real receipts: top clips with real view counts cascade in, then the grand-total hammer.
export const ReceiptStrip: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const totalAt = 20 + TOP_CLIPS.length * 8 + 12;
  const totalS = spring({ frame: frame - totalAt, fps, config: { damping: 200, stiffness: 100, mass: 0.6 } });

  return (
    <AbsoluteFill style={{ backgroundColor: '#0a0b14', padding: '70px 110px', justifyContent: 'center' }}>
      <div style={{ fontFamily: poppins, fontWeight: 600, fontSize: 18, letterSpacing: '4px', textTransform: 'uppercase', color: 'rgba(160,139,236,0.75)', marginBottom: 26 }}>
        Real clips · real views
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {TOP_CLIPS.map((c, i) => {
          const at = 20 + i * 8;
          const s = spring({ frame: frame - at, fps, config: { damping: 200, stiffness: 130, mass: 0.45 } });
          if (frame < at - 2) return null;
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 22, opacity: s, transform: `translateX(${interpolate(s, [0, 1], [-18, 0])}px)`,
            }}>
              <div style={{ fontFamily: poppins, fontWeight: 700, fontSize: 15, color: '#fff', background: PLAT[c.platform], borderRadius: 7, padding: '4px 12px', minWidth: 96, textAlign: 'center' }}>{c.platform}</div>
              <div style={{ flex: 1, fontFamily: poppins, fontWeight: 400, fontSize: 30, color: 'rgba(255,255,255,0.9)' }}>“{c.text}”</div>
              <div style={{ fontFamily: mono, fontWeight: 700, fontSize: 34, color: COLORS.white }}>{c.viewsFmt}</div>
            </div>
          );
        })}
      </div>

      {/* grand total hammer */}
      <div style={{ marginTop: 40, display: 'flex', alignItems: 'baseline', gap: 22, opacity: totalS, transform: `translateY(${interpolate(totalS, [0, 1], [20, 0])}px)` }}>
        <span style={{ fontFamily: poppins, fontWeight: 800, fontSize: 110, color: COLORS.indigo, lineHeight: 1, textShadow: '0 0 50px rgba(111,0,255,0.5)' }}>{GRAND_TOTAL_VIEWS_FMT}</span>
        <span style={{ fontFamily: poppins, fontWeight: 300, fontSize: 40, color: COLORS.lavender }}>
          views · <Odometer target={TOTAL_CLIPS} delay={totalAt} dur={40} format={fmtCommas} style={{ fontWeight: 600, color: COLORS.white }} /> clips
        </span>
      </div>
    </AbsoluteFill>
  );
};
