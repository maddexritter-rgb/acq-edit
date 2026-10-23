import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { loadFont as loadMono } from '@remotion/google-fonts/JetBrainsMono';
import { COLORS } from '../constants';
import { GlassPanel } from './GlassPanel';

const { fontFamily: poppins } = loadPoppins();
const { fontFamily: mono } = loadMono();
const GREEN = '#27c93f';

// Plain-English narration line — the layer that makes the demo legible to a non-technical viewer.
export const NarratorChip: React.FC<{ caption: string; at?: number }> = ({ caption, at = 4 }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f - at, fps, config: { damping: 200, stiffness: 140, mass: 0.5 } });
  return (
    <div style={{ position: 'absolute', bottom: 80, left: 0, right: 0, display: 'flex', justifyContent: 'center', opacity: s, transform: `translateY(${interpolate(s, [0, 1], [20, 0])}px)` }}>
      <GlassPanel dark radius={100} blur={18} sheen={false} style={{ padding: '15px 36px' }}>
        <span style={{ fontFamily: poppins, fontWeight: 700, fontSize: 40, color: '#fff', textShadow: '0 1px 4px rgba(0,0,0,0.6)' }}>{caption}</span>
      </GlassPanel>
    </div>
  );
};

// INPUT: a real 90-minute Alex episode in a glass media player (recognizable = legible).
export const LongVideoPlayer: React.FC<{ caption: string }> = ({ caption }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 90, mass: 0.7 } });
  const push = interpolate(f, [0, 70], [1.06, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ transform: `scale(${interpolate(s, [0, 1], [0.95, 1]) * push})`, opacity: s, marginBottom: 40 }}>
        <GlassPanel radius={18} sheen={false} style={{ width: 1180, padding: 0, overflow: 'hidden' }}>
          <div style={{ position: 'relative', width: 1180, height: 663, background: '#000' }}>
            <Img src={staticFile('recordings/source_frame.jpg')} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(0,0,0,0.35) 0%, transparent 30%, transparent 65%, rgba(0,0,0,0.6) 100%)' }} />
            {/* session label */}
            <div style={{ position: 'absolute', top: 22, left: 26, display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(0,0,0,0.5)', borderRadius: 100, padding: '8px 18px', backdropFilter: 'blur(8px)' }}>
              <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#ff3b3b' }} />
              <span style={{ fontFamily: poppins, fontWeight: 600, fontSize: 20, color: '#fff', letterSpacing: '0.5px' }}>Stay In A Great Mood</span>
            </div>
            {/* play button */}
            <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: 110, height: 110, borderRadius: '50%', background: 'rgba(0,0,0,0.55)', border: '2px solid rgba(255,255,255,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: 0, height: 0, borderTop: '20px solid transparent', borderBottom: '20px solid transparent', borderLeft: '34px solid #fff', marginLeft: 8 }} />
            </div>
            {/* progress + duration */}
            <div style={{ position: 'absolute', bottom: 26, left: 28, right: 28 }}>
              <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.3)' }}><div style={{ width: '35%', height: '100%', borderRadius: 3, background: COLORS.indigo }} /></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, fontFamily: mono, fontSize: 18, color: '#fff' }}><span>24:11</span><span>1:07:48</span></div>
            </div>
          </div>
        </GlassPanel>
      </div>
      <NarratorChip caption={caption} />
    </AbsoluteFill>
  );
};

export const PromptShot: React.FC<{ caption: string }> = ({ caption }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 110, mass: 0.6 } });
  const push = interpolate(f, [0, 48], [1.08, 1], { extrapolateRight: 'clamp' });
  const prompt = 'claude "make shorts from this episode"';
  const chars = Math.floor(interpolate(f, [6, 38], [0, prompt.length], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ transform: `scale(${interpolate(s, [0, 1], [0.96, 1]) * push})`, opacity: s, marginBottom: 40 }}>
        <GlassPanel radius={18} style={{ width: 1120, padding: '46px 52px' }}>
          <div style={{ fontFamily: mono, fontSize: 44, color: '#fff', letterSpacing: '-1px' }}>
            <span style={{ color: GREEN }}>➜ </span><span style={{ color: COLORS.lavender }}>~/acq </span>{prompt.slice(0, chars)}
            {chars < prompt.length && Math.floor(f / 14) % 2 === 0 && <span style={{ color: COLORS.indigo }}>▊</span>}
          </div>
        </GlassPanel>
      </div>
      <NarratorChip caption={caption} />
    </AbsoluteFill>
  );
};

const STEPS = ['Reads every word', 'Finds the 30 best moments', 'Cuts & reframes each one', 'Adds captions + music'];
export const PipelineShot: React.FC<{ caption: string }> = ({ caption }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 110, mass: 0.6 } });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ transform: `scale(${interpolate(s, [0, 1], [0.96, 1])})`, opacity: s, marginBottom: 40 }}>
        <GlassPanel dark radius={18} style={{ width: 980, padding: '40px 52px' }}>
          {STEPS.map((t, i) => {
            const ss = spring({ frame: f - (6 + i * 8), fps, config: { damping: 200, stiffness: 150, mass: 0.4 } });
            if (f < 6 + i * 8 - 2) return null;
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 18, fontFamily: poppins, fontWeight: 600, fontSize: 38, color: '#fff', opacity: ss, transform: `translateX(${interpolate(ss, [0, 1], [-14, 0])}px)`, marginBottom: i < STEPS.length - 1 ? 22 : 0 }}>
                <span style={{ color: GREEN, fontSize: 34 }}>✓</span>{t}
              </div>
            );
          })}
        </GlassPanel>
      </div>
      <NarratorChip caption={caption} />
    </AbsoluteFill>
  );
};

// Shows the reframe magic: 16:9 episode → a 9:16 frame locks onto the face.
export const ShotReframe: React.FC<{ caption: string }> = ({ caption }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 100, mass: 0.6 } });
  const lock = spring({ frame: f - 14, fps, config: { damping: 200, stiffness: 120, mass: 0.5 } });
  const boxW = 300, boxH = 533; // 9:16
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ position: 'relative', opacity: s, transform: `scale(${interpolate(s, [0, 1], [0.96, 1])})`, marginBottom: 40 }}>
        <div style={{ width: 1100, height: 619, borderRadius: 14, overflow: 'hidden', position: 'relative' }}>
          <Img src={staticFile('recordings/source_frame.jpg')} style={{ width: '100%', height: '100%', objectFit: 'cover', filter: `brightness(${interpolate(lock, [0, 1], [1, 0.45])})` }} />
          {/* 9:16 lock box, centered */}
          <div style={{
            position: 'absolute', top: '50%', left: '50%', width: boxW, height: boxH,
            transform: `translate(-50%,-50%) scale(${interpolate(lock, [0, 1], [1.4, 1])})`,
            border: `3px solid ${COLORS.indigo}`, borderRadius: 8, boxShadow: `0 0 40px rgba(111,0,255,0.7), inset 0 0 0 9999px rgba(0,0,0,${interpolate(lock, [0, 1], [0, 0])})`,
            opacity: lock,
          }}>
            {/* corner brackets */}
            {[[0, 0], [1, 0], [0, 1], [1, 1]].map(([x, y], i) => (
              <div key={i} style={{ position: 'absolute', [x ? 'right' : 'left']: -3, [y ? 'bottom' : 'top']: -3, width: 26, height: 26, borderTop: y ? 'none' : `4px solid ${COLORS.lavender}`, borderBottom: y ? `4px solid ${COLORS.lavender}` : 'none', borderLeft: x ? 'none' : `4px solid ${COLORS.lavender}`, borderRight: x ? `4px solid ${COLORS.lavender}` : 'none' }} />
            ))}
            <div style={{ position: 'absolute', top: -34, left: 0, fontFamily: mono, fontSize: 16, color: COLORS.lavender, whiteSpace: 'nowrap' }}>● face locked</div>
          </div>
        </div>
      </div>
      <NarratorChip caption={caption} />
    </AbsoluteFill>
  );
};
