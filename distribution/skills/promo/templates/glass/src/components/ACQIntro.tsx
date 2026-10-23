import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont } from '@remotion/google-fonts/Poppins';
import { COLORS, SPRING_SNAPPY } from '../constants';

const { fontFamily } = loadFont();

interface Props {
  line1: string;
  indigoWord?: string; // word(s) rendered in Electric Indigo
  sub?: string;
}

export const ACQIntro: React.FC<Props> = ({ line1, indigoWord, sub }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headSpring = spring({ frame, fps, config: SPRING_SNAPPY, delay: 4 });
  const headY = interpolate(headSpring, [0, 1], [50, 0]);
  const headOpacity = headSpring;

  const subSpring = spring({ frame, fps, config: SPRING_SNAPPY, delay: 14 });
  const subY = interpolate(subSpring, [0, 1], [30, 0]);

  const lineSpring = spring({ frame, fps, config: SPRING_SNAPPY, delay: 8 });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.sambucus,
        justifyContent: 'center',
        alignItems: 'flex-start',
        padding: '0 140px',
        flexDirection: 'column',
        gap: 0,
      }}
    >
      {/* Indigo left accent bar */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: '50%',
          transform: 'translateY(-50%)',
          width: 6,
          height: interpolate(lineSpring, [0, 1], [0, 200]),
          backgroundColor: COLORS.indigo,
          borderRadius: '0 4px 4px 0',
        }}
      />

      {/* Main headline */}
      <div
        style={{
          transform: `translateY(${headY}px)`,
          opacity: headOpacity,
          fontFamily,
          fontWeight: 800,
          fontSize: 100,
          color: COLORS.white,
          lineHeight: 1.05,
          letterSpacing: '-3px',
          textTransform: 'uppercase',
          maxWidth: 1400,
        }}
      >
        {line1}
        {indigoWord && (
          <span style={{ color: COLORS.indigo }}>{indigoWord}</span>
        )}
        <span style={{ color: COLORS.indigo }}>.</span>
      </div>

      {/* Sub line */}
      {sub && (
        <div
          style={{
            transform: `translateY(${subY}px)`,
            opacity: subSpring,
            fontFamily,
            fontWeight: 300,
            fontSize: 40,
            color: COLORS.lavender,
            marginTop: 28,
            letterSpacing: '0px',
          }}
        >
          {sub}
        </div>
      )}

      {/* Bottom rule */}
      <div
        style={{
          position: 'absolute',
          bottom: 72,
          left: 140,
          right: 140,
          height: 1,
          backgroundColor: `rgba(111,0,255,0.3)`,
          opacity: headOpacity,
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: 72,
          left: 140,
          width: interpolate(lineSpring, [0, 1], [0, 300]),
          height: 1,
          backgroundColor: COLORS.indigo,
        }}
      />
    </AbsoluteFill>
  );
};
