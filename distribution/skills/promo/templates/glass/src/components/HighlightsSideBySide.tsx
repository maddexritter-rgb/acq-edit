import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { loadFont as loadMono } from '@remotion/google-fonts/JetBrainsMono';
import { COLORS } from '../constants';
import { GlassPanel } from './GlassPanel';
import { GlassBrowser } from './GlassBrowser';
import { NarratorChip } from './CreateShots';

const { fontFamily: poppins } = loadPoppins();
const { fontFamily: mono } = loadMono();
const GREEN = '#27c93f';
const rand = (n: number) => { const x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); };

const PROMPT = '$ acq highlights --auto';
const LOGS = ['fetch latest long-form', 'rank + cut highlight', 'title + thumbnail', 'drive publish wizard', 'schedule upload', 'write 3 A/B titles'];
const CHARS = '01<>{}[]/=;:$#λΣ0123456789ACQ▸'.split('');

// The code (terminal, faintly "matrixing") side-by-side with the automation actually running.
export const HighlightsSideBySide: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - 2, fps, config: { damping: 200, stiffness: 100, mass: 0.6 } });
  const chars = Math.floor(interpolate(frame, [6, 34], [0, PROMPT.length], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));

  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', gap: 40, alignItems: 'center', opacity: s, transform: `scale(${interpolate(s, [0, 1], [0.97, 1])})` }}>
        {/* LEFT — terminal / code */}
        <GlassPanel dark radius={16} sheen={false} style={{ width: 720, height: 620, padding: '34px 38px', position: 'relative', overflow: 'hidden' }}>
          {/* faint matrix backdrop */}
          {Array.from({ length: 16 }).map((_, c) => {
            const head = (frame * (0.3 + rand(c) * 0.5) + rand(c + 9) * 30) % 26;
            return (
              <div key={c} style={{ position: 'absolute', left: `${(c / 16) * 100}%`, top: 0, fontFamily: mono, fontSize: 22, lineHeight: 1.15 }}>
                {Array.from({ length: 22 }).map((__, r) => {
                  const d = head - r; const on = d >= 0 && d < 8;
                  if (!on) return <div key={r} style={{ height: 25 }} />;
                  return <div key={r} style={{ height: 25, color: d < 1 ? COLORS.lavender : COLORS.indigo, opacity: d < 1 ? 0.5 : Math.max(0, 0.28 - d * 0.03) }}>{CHARS[Math.floor(rand(c * 50 + r + Math.floor(frame / 6)) * CHARS.length)]}</div>;
                })}
              </div>
            );
          })}
          {/* terminal content */}
          <div style={{ position: 'relative', zIndex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 18 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: GREEN, boxShadow: `0 0 8px ${GREEN}` }} />
              <span style={{ fontFamily: poppins, fontWeight: 600, fontSize: 12, letterSpacing: '3px', textTransform: 'uppercase', color: 'rgba(160,139,236,0.8)' }}>Live · the code</span>
            </div>
            <div style={{ fontFamily: mono, fontSize: 25, color: '#fff' }}>
              <span style={{ color: GREEN }}>➜ </span>{PROMPT.slice(0, chars)}{chars < PROMPT.length && Math.floor(frame / 14) % 2 === 0 && <span style={{ color: COLORS.indigo }}>▊</span>}
            </div>
            <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 14 }}>
              {LOGS.map((l, i) => {
                const at = 40 + i * 11;
                const ls = spring({ frame: frame - at, fps, config: { damping: 200, stiffness: 150, mass: 0.4 } });
                if (frame < at - 2) return null;
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 13, fontFamily: mono, fontSize: 22, color: 'rgba(255,255,255,0.92)', opacity: ls, transform: `translateX(${interpolate(ls, [0, 1], [-10, 0])}px)` }}>
                    <span style={{ color: GREEN }}>✓</span>{l}
                  </div>
                );
              })}
            </div>
          </div>
        </GlassPanel>

        {/* RIGHT — the automation actually running */}
        <GlassBrowser src="recordings/highlights_crop.mov" urlText="studio.youtube.com/@MoreMozi" playbackRate={5} startFrom={120} style={{ width: 1060, height: 620 }} />
      </div>
      <NarratorChip caption="The code — and the automation it drives." />
    </AbsoluteFill>
  );
};
