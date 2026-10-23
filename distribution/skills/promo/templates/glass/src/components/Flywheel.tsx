import React from 'react';
import { AbsoluteFill, OffthreadVideo, Img, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { loadFont as loadMono } from '@remotion/google-fonts/JetBrainsMono';
import { COLORS } from '../constants';
import { GlassPanel } from './GlassPanel';
import { NarratorChip } from './CreateShots';

const { fontFamily: poppins } = loadPoppins();
const { fontFamily: mono } = loadMono();
const GREEN = '#27c93f';

// ── RAW SESSION: the live L1 Q&A playing in a glass media player (the irreplaceable proof) ──
export const RawSessionPlayer: React.FC<{ caption: string }> = ({ caption }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 90, mass: 0.7 } });
  const push = interpolate(f, [0, 80], [1.05, 1], { extrapolateRight: 'clamp' });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ transform: `scale(${interpolate(s, [0, 1], [0.95, 1]) * push})`, opacity: s, marginBottom: 40 }}>
        <GlassPanel radius={18} sheen={false} style={{ width: 1180, padding: 0, overflow: 'hidden' }}>
          <div style={{ position: 'relative', width: 1180, height: 663, background: '#000' }}>
            <OffthreadVideo src={staticFile('recordings/l1_raw.mp4')} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(0,0,0,0.35) 0%, transparent 28%, transparent 64%, rgba(0,0,0,0.62) 100%)' }} />
            <div style={{ position: 'absolute', top: 22, left: 26, display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(0,0,0,0.5)', borderRadius: 100, padding: '8px 18px', backdropFilter: 'blur(8px)' }}>
              <div style={{ width: 9, height: 9, borderRadius: '50%', background: '#ff3b3b' }} />
              <span style={{ fontFamily: poppins, fontWeight: 600, fontSize: 20, color: '#fff', letterSpacing: '0.5px' }}>L1 DAY 2 · LIVE Q&amp;A</span>
            </div>
            <div style={{ position: 'absolute', bottom: 26, left: 28, right: 28 }}>
              <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.3)' }}><div style={{ width: '46%', height: '100%', borderRadius: 3, background: COLORS.indigo }} /></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, fontFamily: mono, fontSize: 18, color: '#fff' }}><span>50:42</span><span>1:50:11</span></div>
            </div>
          </div>
        </GlassPanel>
      </div>
      <NarratorChip caption={caption} />
    </AbsoluteFill>
  );
};

// ── L1 PROMPT: one command kicks the whole pipeline ──
export const L1Prompt: React.FC<{ caption: string }> = ({ caption }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 110, mass: 0.6 } });
  const push = interpolate(f, [0, 48], [1.07, 1], { extrapolateRight: 'clamp' });
  const prompt = 'claude "cut the L1 Q&A into mids"';
  const chars = Math.floor(interpolate(f, [6, 40], [0, prompt.length], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ transform: `scale(${interpolate(s, [0, 1], [0.96, 1]) * push})`, opacity: s, marginBottom: 40 }}>
        <GlassPanel radius={18} style={{ width: 1180, padding: '46px 52px' }}>
          <div style={{ fontFamily: mono, fontSize: 44, color: '#fff', letterSpacing: '-1px' }}>
            <span style={{ color: GREEN }}>➜ </span><span style={{ color: COLORS.lavender }}>~/alex </span>{prompt.slice(0, chars)}
            {chars < prompt.length && Math.floor(f / 14) % 2 === 0 && <span style={{ color: COLORS.indigo }}>▊</span>}
          </div>
        </GlassPanel>
      </div>
      <NarratorChip caption={caption} />
    </AbsoluteFill>
  );
};

// ── L1 PIPELINE: the trigger→action→result steps for a Q&A ──
const STEPS = ['Reads every question + answer', 'Finds the moments that land', 'Cuts, reframes & captions each', 'Audits itself, then ships'];
export const L1Pipeline: React.FC<{ caption: string }> = ({ caption }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 110, mass: 0.6 } });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ transform: `scale(${interpolate(s, [0, 1], [0.96, 1])})`, opacity: s, marginBottom: 40 }}>
        <GlassPanel dark radius={18} style={{ width: 1040, padding: '40px 54px' }}>
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

// ── HERO CLIP: one real finished clip playing big in a phone frame ──
export const HeroClipPlayer: React.FC<{ clip: string; title: string; caption: string }> = ({ clip, title, caption }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 100, mass: 0.6 } });
  const w = 482, h = 857; // 9:16
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 60, opacity: s, transform: `translateY(${interpolate(s, [0, 1], [24, 0])}px)`, marginBottom: 30 }}>
        <div style={{ width: w, height: h, borderRadius: 30, overflow: 'hidden', background: '#000', border: '3px solid rgba(160,139,236,0.45)', boxShadow: '0 30px 90px rgba(0,0,0,0.6), 0 0 60px rgba(111,0,255,0.25)' }}>
          <OffthreadVideo src={staticFile(`clips/${clip}.mp4`)} startFrom={Math.round(8 * 30)} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
        <div style={{ width: 560 }}>
          <div style={{ fontFamily: poppins, fontWeight: 600, fontSize: 18, color: COLORS.lavender, letterSpacing: '3px', textTransform: 'uppercase', marginBottom: 16 }}>One moment from the Q&amp;A</div>
          <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 62, lineHeight: 1.04, letterSpacing: '-2px', color: '#fff' }}>{title}</div>
          {(() => {
            const cs = spring({ frame: f - 18, fps, config: { damping: 200, stiffness: 130, mass: 0.5 } });
            return (
              <div style={{ marginTop: 26, opacity: cs, transform: `translateY(${interpolate(cs, [0, 1], [14, 0])}px)` }}>
                <div style={{ fontFamily: poppins, fontWeight: 600, fontSize: 32, color: '#fff', lineHeight: 1.25 }}>Cut, reframed, captioned, scored.</div>
                <div style={{ fontFamily: poppins, fontWeight: 400, fontSize: 26, color: COLORS.lavender, marginTop: 8 }}>Start to finish — no editor touched it.</div>
              </div>
            );
          })()}
        </div>
      </div>
      <NarratorChip caption={caption} />
    </AbsoluteFill>
  );
};

// ── CONTENT FLYWHEEL: the loop — each turn compounds. AI is the accelerant at the cut step ──
const NODES = [
  { label: 'L1 WORKSHOP', sub: 'the $5k front-end' },
  { label: 'LIVE Q&A', sub: 'Alex, day two' },
  { label: 'AI CUTS IT', sub: 'one operator', ai: true },
  { label: 'MIDS + SHORTS', sub: 'highlights + socials' },
  { label: 'NEW CLIENTS', sub: 'buy the workshop' },
];
const RADIUS = 300, RING_BOX = 820;
export const ContentFlywheel: React.FC = () => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const circumference = 2 * Math.PI * RADIUS;
  const drawn = interpolate(frame, [10, 64], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const dashOffset = circumference * (1 - drawn);
  const pulseAngle = interpolate(frame, [64, 64 + 4 * 30], [0, 360], { extrapolateRight: 'extend' }) - 90;
  const centerS = spring({ frame: frame - 74, fps, config: { damping: 200, stiffness: 110, mass: 0.6 } });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundImage: `linear-gradient(rgba(111,0,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(111,0,255,0.035) 1px, transparent 1px)`, backgroundSize: '64px 64px' }} />
      <div style={{ position: 'relative', width: RING_BOX, height: RING_BOX }}>
        <svg width={RING_BOX} height={RING_BOX} style={{ position: 'absolute', inset: 0 }}>
          <circle cx={RING_BOX / 2} cy={RING_BOX / 2} r={RADIUS} fill="none" stroke="rgba(160,139,236,0.12)" strokeWidth={2} />
          <circle cx={RING_BOX / 2} cy={RING_BOX / 2} r={RADIUS} fill="none" stroke={COLORS.indigo} strokeWidth={3}
            strokeDasharray={circumference} strokeDashoffset={dashOffset} strokeLinecap="round"
            transform={`rotate(-90 ${RING_BOX / 2} ${RING_BOX / 2})`} style={{ filter: 'drop-shadow(0 0 8px rgba(111,0,255,0.6))' }} />
        </svg>
        {frame >= 64 && (
          <div style={{ position: 'absolute', left: '50%', top: '50%', transform: `rotate(${pulseAngle}deg) translateX(${RADIUS}px)`, transformOrigin: '0 0' }}>
            <div style={{ width: 22, height: 22, borderRadius: '50%', background: GREEN, transform: 'translate(-50%,-50%)', boxShadow: '0 0 24px 6px rgba(39,201,63,0.7)' }} />
          </div>
        )}
        {NODES.map((n, i) => {
          const angle = (i * 72 - 90) * (Math.PI / 180);
          const x = RING_BOX / 2 + RADIUS * Math.cos(angle);
          const y = RING_BOX / 2 + RADIUS * Math.sin(angle);
          const s = spring({ frame: frame - (64 + i * 8), fps, config: { damping: 200, stiffness: 130, mass: 0.5 } });
          return (
            <div key={n.label} style={{ position: 'absolute', left: x, top: y, transform: `translate(-50%,-50%) scale(${interpolate(s, [0, 1], [0.6, 1])})`, opacity: s, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, width: 230 }}>
              <div style={{ background: n.ai ? 'rgba(111,0,255,0.32)' : COLORS.sambucus, border: `2px solid ${n.ai ? COLORS.lavender : COLORS.indigo}`, borderRadius: 12, padding: '12px 22px', boxShadow: n.ai ? '0 0 40px rgba(160,139,236,0.6)' : '0 0 30px rgba(111,0,255,0.3)', fontFamily: poppins, fontWeight: 800, fontSize: 25, color: COLORS.white, letterSpacing: '0.5px', whiteSpace: 'nowrap' }}>{n.label}</div>
              <div style={{ fontFamily: poppins, fontWeight: 300, fontSize: 17, color: COLORS.lavender }}>{n.sub}</div>
            </div>
          );
        })}
        <div style={{ position: 'absolute', left: '50%', top: '50%', transform: `translate(-50%,-50%) scale(${interpolate(centerS, [0, 1], [0.8, 1])})`, opacity: centerS, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <div style={{ fontSize: 76, color: COLORS.indigo, lineHeight: 1, marginBottom: 6 }}>∞</div>
          <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 32, color: COLORS.white, letterSpacing: '0.5px' }}>THE CONTENT<br />FLYWHEEL</div>
          <div style={{ fontFamily: poppins, fontWeight: 300, fontSize: 18, color: COLORS.lavender, marginTop: 8 }}>every turn compounds</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── COMPOUNDS: the deck's recap close ("Attention compounds. Trust compounds. Systems compound.
// Genius businesses compound.") as DESIGNED glass chips that build — not raw centered text. ──
const COMPOUNDS: [string, string][] = [
  ['Attention', 'compounds.'],
  ['Trust', 'compounds.'],
  ['Systems', 'compound.'],
];
export const CompoundsBeat: React.FC = () => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const exit = interpolate(f, [124, 138], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const cap = spring({ frame: f - 62, fps, config: { damping: 200, stiffness: 120, mass: 0.55 } });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 18 }}>
      <AbsoluteFill style={{ background: 'rgba(9,10,20,0.85)', opacity: exit, zIndex: 0 }} />
      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
        {COMPOUNDS.map(([w, c], i) => {
          const s = spring({ frame: f - (6 + i * 15), fps, config: { damping: 200, stiffness: 130, mass: 0.5 } });
          return (
            <GlassPanel key={i} dark radius={100} sheen={false} style={{ padding: '14px 46px', opacity: s * exit, transform: `translateY(${interpolate(s, [0, 1], [22, 0])}px) scale(${interpolate(s, [0, 1], [0.92, 1])})` }}>
              <span style={{ fontFamily: poppins, fontWeight: 800, fontSize: 54, letterSpacing: '-1px', color: '#fff' }}>{w} </span>
              <span style={{ fontFamily: poppins, fontWeight: 800, fontSize: 54, letterSpacing: '-1px', color: COLORS.indigo }}>{c}</span>
            </GlassPanel>
          );
        })}
        <div style={{ marginTop: 18, opacity: cap * exit, transform: `scale(${interpolate(cap, [0, 1], [0.9, 1])})`, fontFamily: poppins, fontWeight: 800, fontSize: 42, letterSpacing: '2px', textTransform: 'uppercase', color: '#d9ccfa', textShadow: '0 0 24px rgba(124,77,255,0.95)' }}>
          Genius businesses compound.
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── AUTO-POST: the REAL publisher (terminal) driving YouTube Studio (screen recording), side by side ──
// Terminal log mirrors the real schedule_drafts.py output; right panel is the actual screen recording.
const TERM: { d: number; t: string; k: string }[] = [
  { d: 0, t: '➜  yt-draft-publisher  source .env', k: 'cmd' },
  { d: 6, t: '➜  yt-draft-publisher  python3 scripts/schedule_drafts.py', k: 'cmd' },
  { d: 16, t: 'Navigating to YouTube Studio…', k: 'dim' },
  { d: 23, t: 'Logged in → Hormozi Highlights ✓', k: 'dim' },
  { d: 29, t: 'publishDraft injected.', k: 'dim' },
  { d: 37, t: '[slot 11] "Scaling a Pro Volleyball Brand…"', k: 'w' },
  { d: 44, t: '   Details ✓  Monetization On ✓', k: 'dim' },
  { d: 51, t: '   Ad suitability → Safe for ads ✓', k: 'dim' },
  { d: 58, t: '   Visibility → Public → Schedule ✓', k: 'dim' },
  { d: 66, t: '   OK   scheduled · Jun 28 · 9:00 AM ET', k: 'g' },
  { d: 78, t: '[slot 12] "Kill the Customer That’s…"    OK', k: 'g' },
  { d: 88, t: '[slot 13] "Helping a $20M Fence Co…"     OK', k: 'g' },
  { d: 98, t: '[slot 14] "Hire the Right Leadership…"   OK', k: 'g' },
  { d: 110, t: 'Done. 15 drafts scheduled this run.', k: 'wb' },
  { d: 118, t: '1,910 published all-time · 0 editors', k: 'lav' },
];
const TERM_COL: Record<string, string> = { cmd: '#e6e6ee', dim: 'rgba(255,255,255,0.5)', w: '#fff', g: GREEN, wb: '#fff', lav: COLORS.lavender };
export const AutoPostScheduler: React.FC<{ caption: string }> = ({ caption }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const s = spring({ frame: f, fps, config: { damping: 200, stiffness: 100, mass: 0.6 } });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      {/* header */}
      <div style={{ position: 'absolute', top: 92, display: 'flex', alignItems: 'center', gap: 16, opacity: s }}>
        <span style={{ fontFamily: poppins, fontWeight: 800, fontSize: 30, color: '#fff', letterSpacing: '0.5px' }}>POSTING AUTOMATION</span>
        <span style={{ fontFamily: poppins, fontWeight: 400, fontSize: 22, color: COLORS.lavender }}>@MoreMozi · the highlights channel</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 7, marginLeft: 4 }}>
          <span style={{ width: 11, height: 11, borderRadius: '50%', background: GREEN, boxShadow: `0 0 12px ${GREEN}`, opacity: 0.55 + 0.45 * Math.sin(f / 4) }} />
          <span style={{ fontFamily: poppins, fontWeight: 700, fontSize: 16, letterSpacing: '2px', color: GREEN }}>LIVE</span>
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'stretch', gap: 34, opacity: s, transform: `scale(${interpolate(s, [0, 1], [0.97, 1])})`, marginTop: 40 }}>
        {/* LEFT — live terminal (the real publisher) */}
        <div style={{ width: 600, height: 520, borderRadius: 14, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.12)', background: '#0a0b14', boxShadow: '0 24px 70px rgba(0,0,0,0.55)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ height: 40, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px', background: 'rgba(255,255,255,0.05)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
            {['#ff5f56', '#ffbd2e', '#27c93f'].map((c) => <div key={c} style={{ width: 11, height: 11, borderRadius: '50%', background: c }} />)}
            <span style={{ marginLeft: 12, fontFamily: mono, fontSize: 14, color: 'rgba(255,255,255,0.5)' }}>schedule_drafts.py — zsh</span>
          </div>
          <div style={{ flex: 1, padding: '16px 20px', overflow: 'hidden' }}>
            {TERM.map((ln, i) => {
              if (f < ln.d) return null;
              const o = interpolate(f, [ln.d, ln.d + 4], [0, 1], { extrapolateRight: 'clamp' });
              return (
                <div key={i} style={{ fontFamily: mono, fontSize: 16, lineHeight: 1.6, color: TERM_COL[ln.k], fontWeight: ln.k === 'wb' ? 700 : 400, opacity: o, whiteSpace: 'pre' }}>
                  {ln.k === 'cmd' ? <><span style={{ color: GREEN }}>{ln.t.slice(0, 3)}</span>{ln.t.slice(3)}</> : ln.t}
                </div>
              );
            })}
            {Math.floor(f / 14) % 2 === 0 && <span style={{ fontFamily: mono, fontSize: 16, color: COLORS.indigo }}>▊</span>}
          </div>
        </div>

        {/* RIGHT — the actual screen recording, cropped to JUST the YouTube Studio UI (no browser tab / URL) */}
        <div style={{ width: 1180, height: 520, borderRadius: 14, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.12)', background: '#000', boxShadow: '0 24px 70px rgba(0,0,0,0.55)' }}>
          <OffthreadVideo src={staticFile('recordings/highlights_auto.mp4')} startFrom={Math.round(1 * 30)} playbackRate={2.3} muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      </div>
      <NarratorChip caption={caption} />
    </AbsoluteFill>
  );
};
