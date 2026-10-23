import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { COLORS } from '../constants';

const { fontFamily: poppins } = loadPoppins();

const OLD = ['1 editor · $2,000/mo', '~10 hours per clip', '3 clips a week'];
const NEW = ['0 editors · $0', '10 minutes · 30 clips', '400+ a month'];

// The deprivation split: the old way (greyed, heavy) vs the workflow (vibrant, exploding).
export const BeforeAfter: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const leftS = spring({ frame: frame - 4, fps, config: { damping: 200, stiffness: 90, mass: 0.7 } });
  const rightS = spring({ frame: frame - 30, fps, config: { damping: 200, stiffness: 110, mass: 0.6 } });

  return (
    <AbsoluteFill style={{ flexDirection: 'row', backgroundColor: '#0a0b14' }}>
      {/* OLD */}
      <div style={{
        flex: 1, padding: '0 90px', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 26,
        filter: `grayscale(1)`, opacity: leftS * 0.62, transform: `translateX(${interpolate(leftS, [0, 1], [-30, 0])}px)`,
      }}>
        <Head sub="The old way" color="rgba(180,180,190,0.8)" title="Manual" titleColor="#9aa0ad" />
        {OLD.map((t, i) => <Stat key={i} text={t} color="#7d828f" dim />)}
      </div>

      {/* divider + VS */}
      <div style={{ width: 2, background: `linear-gradient(180deg, transparent, ${COLORS.indigo}, transparent)`, position: 'relative' }}>
        <div style={{
          position: 'absolute', top: '50%', left: '50%', transform: `translate(-50%,-50%) scale(${rightS})`,
          width: 78, height: 78, borderRadius: '50%', background: COLORS.sambucus, border: `2px solid ${COLORS.indigo}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: poppins, fontWeight: 800, fontSize: 26, color: COLORS.white,
          boxShadow: `0 0 40px rgba(111,0,255,0.5)`,
        }}>VS</div>
      </div>

      {/* NEW */}
      <div style={{
        flex: 1, padding: '0 90px', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 26,
        opacity: rightS, transform: `translateX(${interpolate(rightS, [0, 1], [30, 0])}px)`,
      }}>
        <Head sub="With the workflow" color={COLORS.lavender} title="Automated" titleColor={COLORS.white} glow />
        {NEW.map((t, i) => <Stat key={i} text={t} color={COLORS.white} accent />)}
      </div>
    </AbsoluteFill>
  );
};

const Head: React.FC<{ sub: string; title: string; color: string; titleColor: string; glow?: boolean }> = ({ sub, title, color, titleColor, glow }) => (
  <div style={{ marginBottom: 10 }}>
    <div style={{ fontFamily: poppins, fontWeight: 600, fontSize: 16, letterSpacing: '3px', textTransform: 'uppercase', color }}>{sub}</div>
    <div style={{ fontFamily: poppins, fontWeight: 800, fontSize: 72, color: titleColor, lineHeight: 1.05, textShadow: glow ? '0 0 40px rgba(111,0,255,0.4)' : 'none' }}>{title}</div>
  </div>
);

const Stat: React.FC<{ text: string; color: string; dim?: boolean; accent?: boolean }> = ({ text, color, dim, accent }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
    <div style={{ width: 10, height: 10, borderRadius: '50%', background: dim ? '#5a5f6b' : '#27c93f', boxShadow: accent ? '0 0 12px #27c93f' : 'none' }} />
    <span style={{ fontFamily: poppins, fontWeight: dim ? 400 : 600, fontSize: 34, color }}>{text}</span>
  </div>
);
