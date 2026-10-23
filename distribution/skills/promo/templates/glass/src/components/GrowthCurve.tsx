import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { GlassBG } from './GlassBG';
import { COLORS } from '../constants';

const { fontFamily: poppins } = loadPoppins();

// The exclamation point: a compounding exponential growth curve, milestones plotting on as it sweeps,
// climaxing on 3 -> 200 + ACQ logo. v2: 2x the "sexy spice" — comet draw head, glowing reveal fill,
// ring-pulse milestones, climax flash + rising sparks, breathing glow. Years best-guess, extends to 2026.
const MILES = [
  { x: 0.05, label: 'Day Zero', year: '2020' },
  { x: 0.24, label: 'The Mission', year: '2021' },
  { x: 0.45, label: '$100M Leads', year: '2023' },
  { x: 0.63, label: 'Vegas HQ + L1', year: '2024' },
  { x: 0.81, label: 'Sharran joins', year: '2025' },
  { x: 0.96, label: '$100M Money Models', year: '2025' },
];
const TICKS = [{ yr: '2020', xx: 0 }, { yr: '2022', xx: 0.33 }, { yr: '2024', xx: 0.67 }, { yr: '2026', xx: 1 }];

const PL = 200, PR = 1740, PB = 940, PT = 250;
const K = 3.1;
const yAt = (x: number) => (Math.exp(K * x) - 1) / (Math.exp(K) - 1);
const px = (x: number) => PL + x * (PR - PL);
const py = (x: number) => PB - yAt(x) * (PB - PT);

export const GrowthCurve: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const N = 160;
  let d = '', area = `M${px(0).toFixed(1)},${PB} `;
  for (let i = 0; i <= N; i++) { const x = i / N; const X = px(x).toFixed(1), Y = py(x).toFixed(1); d += (i === 0 ? 'M' : 'L') + X + ',' + Y + ' '; area += `L${X},${Y} `; }
  area += `L${px(1).toFixed(1)},${PB} Z`;

  const drawEnd = 20 + 3.4 * fps;
  const draw = interpolate(frame, [20, drawEnd], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const LEN = 4400;
  const climaxAt = drawEnd + 0.15 * fps;
  const climax = interpolate(frame, [drawEnd, climaxAt + 0.7 * fps], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const teamN = Math.round(interpolate(climax, [0, 1], [3, 200]));
  const statS = spring({ frame: frame - Math.round(climaxAt), fps, config: { damping: 140, stiffness: 120, mass: 0.7 } });
  const logoS = spring({ frame: frame - Math.round(climaxAt + 0.7 * fps), fps, config: { damping: 200, stiffness: 90, mass: 0.6 } });
  const flash = interpolate(frame, [climaxAt - 2, climaxAt + 5, climaxAt + 26], [0, 0.85, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const breathe = 0.82 + 0.18 * Math.sin(frame / 16);              // glow pulse on the hold
  const headX = px(draw), headY = py(draw);
  const cometOp = interpolate(draw, [0, 0.04, 0.97, 1], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const curveGlow = (draw < 1 ? 22 : 22 * breathe);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.sambucus }}>
      <GlassBG />
      <AbsoluteFill>
        <svg viewBox="0 0 1920 1080" style={{ width: '100%', height: '100%' }}>
          <defs>
            <linearGradient id="cg" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={COLORS.lavender} />
              <stop offset="55%" stopColor="#8a5cff" />
              <stop offset="100%" stopColor={COLORS.indigo} />
            </linearGradient>
            <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#8a5cff" stopOpacity={0.5} />
              <stop offset="55%" stopColor={COLORS.indigo} stopOpacity={0.18} />
              <stop offset="100%" stopColor={COLORS.indigo} stopOpacity={0} />
            </linearGradient>
            <radialGradient id="flashg" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#b79bff" stopOpacity={0.9} />
              <stop offset="100%" stopColor="#b79bff" stopOpacity={0} />
            </radialGradient>
            <clipPath id="reveal"><rect x={PL} y={PT - 60} width={Math.max(0, headX - PL)} height={PB - PT + 80} /></clipPath>
          </defs>

          {/* faint gridlines */}
          {[0.25, 0.5, 0.75, 1].map((g, i) => (
            <line key={i} x1={PL} y1={PB - g * (PB - PT)} x2={PR} y2={PB - g * (PB - PT)} stroke={'rgba(160,139,236,0.08)'} strokeWidth={1} />
          ))}
          {/* axes */}
          <line x1={PL} y1={PB} x2={PR} y2={PB} stroke={'rgba(160,139,236,0.30)'} strokeWidth={2} />
          <line x1={PL} y1={PB} x2={PL} y2={PT} stroke={'rgba(160,139,236,0.18)'} strokeWidth={2} />
          {TICKS.map((t, i) => (
            <text key={t.yr} x={px(t.xx)} y={PB + 38} fill={'rgba(255,255,255,0.55)'} fontFamily={poppins} fontWeight={600} fontSize={20} textAnchor={i === 0 ? 'start' : i === TICKS.length - 1 ? 'end' : 'middle'}>{t.yr}</text>
          ))}

          {/* glowing area fill, revealed left-to-right with the draw */}
          <g clipPath="url(#reveal)"><path d={area} fill="url(#ag)" /></g>
          {/* the curve — double stroke (halo + bright core) */}
          <path d={d} fill="none" stroke={COLORS.indigo} strokeWidth={16} strokeLinecap="round" opacity={0.35}
            strokeDasharray={LEN} strokeDashoffset={LEN * (1 - draw)} style={{ filter: `blur(7px)` }} />
          <path d={d} fill="none" stroke="url(#cg)" strokeWidth={9} strokeLinecap="round"
            strokeDasharray={LEN} strokeDashoffset={LEN * (1 - draw)}
            style={{ filter: `drop-shadow(0 0 ${curveGlow}px ${COLORS.indigo})` }} />

          {/* comet draw-head */}
          <circle cx={headX} cy={headY} r={26} fill="url(#flashg)" opacity={cometOp * 0.8} />
          <circle cx={headX} cy={headY} r={9} fill="#ffffff" opacity={cometOp} style={{ filter: `drop-shadow(0 0 14px ${COLORS.lavender})` }} />

          {/* milestone dots — pop + ring pulse as the draw front passes */}
          {MILES.map((m, i) => {
            const prog = interpolate(draw, [m.x, m.x + 0.05], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            if (prog <= 0) return null;
            const cx = px(m.x), cy = py(m.x), up = i % 2 === 0;
            const pop = interpolate(prog, [0, 0.6], [0, 1], { extrapolateRight: 'clamp' });
            const ringR = interpolate(prog, [0, 1], [9, 48]); const ringOp = interpolate(prog, [0, 1], [0.85, 0]);
            return (
              <g key={i}>
                <circle cx={cx} cy={cy} r={ringR} fill="none" stroke={COLORS.lavender} strokeWidth={2} opacity={ringOp} />
                <circle cx={cx} cy={cy} r={9 * pop} fill="#ffffff" style={{ filter: `drop-shadow(0 0 10px ${COLORS.indigo})` }} />
                <text x={cx} y={up ? cy - 30 : cy + 64} fill={COLORS.white} fontFamily={poppins} fontWeight={700} fontSize={23} textAnchor="middle" opacity={pop} style={{ filter: 'drop-shadow(0 2px 6px rgba(0,0,0,0.6))' }}>{m.label}</text>
                <text x={cx} y={up ? cy - 54 : cy + 42} fill={COLORS.lavender} fontFamily={poppins} fontWeight={600} fontSize={16} textAnchor="middle" opacity={pop}>{m.year}</text>
              </g>
            );
          })}
        </svg>

        {/* climax flash behind the stat */}
        <AbsoluteFill style={{ alignItems: 'flex-start', justifyContent: 'flex-start' }}>
          <div style={{ position: 'absolute', left: 80, top: 60, width: 760, height: 420, background: 'radial-gradient(circle, rgba(138,92,255,0.55), transparent 65%)', opacity: flash, filter: 'blur(8px)' }} />
        </AbsoluteFill>

        {/* climax headline — pops in upper-left */}
        <AbsoluteFill style={{ alignItems: 'flex-start', justifyContent: 'flex-start', padding: '120px 0 0 200px', opacity: Math.min(1, statS) }}>
          <div style={{ transform: `scale(${interpolate(statS, [0, 1], [0.7, 1])})`, transformOrigin: 'left top' }}>
            <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 158, lineHeight: 0.95, color: COLORS.white, textShadow: `0 0 ${50 * breathe}px ${COLORS.indigo}` }}>
              3 <span style={{ color: COLORS.lavender }}>&rarr;</span> {teamN}
            </div>
            <div style={{ fontFamily: poppins, fontWeight: 600, fontSize: 30, letterSpacing: 5, color: COLORS.lavender, marginTop: 8 }}>TEAM MEMBERS SINCE DAY ZERO</div>
          </div>
        </AbsoluteFill>

        {/* rising sparks at the climax */}
        <AbsoluteFill style={{ opacity: interpolate(frame, [climaxAt, climaxAt + 6, climaxAt + 55, climaxAt + 75], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>
          {Array.from({ length: 14 }).map((_, i) => {
            const seed = (i * 137.5) % 100 / 100;
            const x0 = 1180 + seed * 620; const rise = ((frame - climaxAt) * (1.4 + seed)) % 240;
            const yy = 760 - rise; const op = interpolate(rise, [0, 40, 200, 240], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            return <div key={i} style={{ position: 'absolute', left: x0, top: yy, width: 4, height: 4, borderRadius: 4, background: COLORS.lavender, opacity: op * 0.8, boxShadow: `0 0 8px ${COLORS.lavender}` }} />;
          })}
        </AbsoluteFill>

        {/* logo (thesis line removed per Maddex 2026-06-14) */}
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'flex-end', paddingBottom: 70, opacity: logoS, transform: `translateY(${interpolate(logoS, [0, 1], [20, 0])}px)` }}>
          <Img src={staticFile('acq-logo-white.png')} style={{ height: 52, filter: `drop-shadow(0 0 ${24 * breathe}px ${COLORS.indigo})` }} />
        </AbsoluteFill>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
