import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont } from '@remotion/google-fonts/Poppins';
import { COLORS, SPRING_SNAPPY, SPRING_SMOOTH } from '../constants';

const { fontFamily } = loadFont();

interface Props {
  metric: string;       // e.g. "30 clips."
  sub: string;          // e.g. "10 minutes."
  tagline?: string;     // optional extra line e.g. "Attention Compounds."
}

export const ACQOutro: React.FC<Props> = ({ metric, sub, tagline }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const metricSpring = spring({ frame, fps, config: SPRING_SNAPPY, delay: 4 });
  const subSpring = spring({ frame, fps, config: SPRING_SNAPPY, delay: 12 });
  const logoSpring = spring({ frame, fps, config: SPRING_SNAPPY, delay: 10 });
  const tagSpring = spring({ frame, fps, config: SPRING_SNAPPY, delay: 16 });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.sambucus,
        justifyContent: 'center',
        alignItems: 'center',
        flexDirection: 'column',
        gap: 0,
      }}
    >
      {/* Radial glow */}
      <div style={{
        position: 'absolute',
        width: 600, height: 600,
        borderRadius: '50%',
        background: `radial-gradient(circle, rgba(111,0,255,0.12) 0%, transparent 70%)`,
        opacity: logoSpring,
      }} />

      {/* Metric */}
      <div style={{
        transform: `translateY(${interpolate(metricSpring, [0, 1], [40, 0])}px)`,
        opacity: metricSpring,
        fontFamily,
        fontWeight: 800,
        fontSize: 120,
        color: COLORS.white,
        letterSpacing: '-4px',
        lineHeight: 1,
        textTransform: 'uppercase',
        position: 'relative', zIndex: 1,
      }}>
        {metric}
      </div>

      {/* Sub */}
      <div style={{
        transform: `translateY(${interpolate(subSpring, [0, 1], [30, 0])}px)`,
        opacity: subSpring,
        fontFamily,
        fontWeight: 300,
        fontSize: 52,
        color: COLORS.lavender,
        marginTop: 12,
        letterSpacing: '0px',
        position: 'relative', zIndex: 1,
      }}>
        {sub}
      </div>

      {/* Optional tagline */}
      {tagline && (
        <div style={{
          transform: `translateY(${interpolate(tagSpring, [0, 1], [20, 0])}px)`,
          opacity: tagSpring,
          fontFamily,
          fontWeight: 600,
          fontSize: 28,
          color: COLORS.indigo,
          marginTop: 32,
          letterSpacing: '2px',
          textTransform: 'uppercase',
          position: 'relative', zIndex: 1,
        }}>
          {tagline}
        </div>
      )}

      {/* Divider */}
      <div style={{
        width: interpolate(logoSpring, [0, 1], [0, 300]),
        height: 1,
        backgroundColor: `rgba(111,0,255,0.4)`,
        marginTop: 52,
        marginBottom: 36,
        position: 'relative', zIndex: 1,
      }} />

      {/* ACQ Logo */}
      <div style={{
        opacity: logoSpring,
        transform: `translateY(${interpolate(logoSpring, [0, 1], [10, 0])}px)`,
        position: 'relative', zIndex: 1,
      }}>
        <Img
          src={staticFile('acq-logo-trim.png')}
          style={{ width: 640, height: 'auto', objectFit: 'contain' }}
        />
      </div>
    </AbsoluteFill>
  );
};
