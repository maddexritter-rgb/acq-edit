import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont } from '@remotion/google-fonts/Poppins';
import { COLORS, SPRING_SNAPPY } from '../constants';

const { fontFamily } = loadFont();

interface Props {
  tag: 'TRIGGER' | 'ACTION' | 'RESULT';
  text: string;
  // If this callout is near the end of its Sequence, pass totalFrames to fade it out
  totalFrames?: number;
}

const TAG_COLORS: Record<string, string> = {
  TRIGGER: COLORS.indigo,
  ACTION: '#2d64e3',    // ACQ Ventures Catalyst Blue (distinct from indigo)
  RESULT: '#27c93f',    // terminal green
};

export const ACQTextCallout: React.FC<Props> = ({ tag, text, totalFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Spring IN
  const inSpring = spring({ frame, fps, config: SPRING_SNAPPY, delay: 0 });
  const y = interpolate(inSpring, [0, 1], [24, 0]);
  const opacity = inSpring;

  // Fade OUT in last 12 frames if totalFrames given
  let outOpacity = 1;
  if (totalFrames) {
    outOpacity = interpolate(frame, [totalFrames - 12, totalFrames], [1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  }

  const tagColor = TAG_COLORS[tag] ?? COLORS.indigo;

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'flex-start',
        padding: '0 64px 68px',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          transform: `translateY(${y}px)`,
          opacity: opacity * outOpacity,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          maxWidth: 860,
        }}
      >
        {/* Tag pill */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            backgroundColor: `${tagColor}22`,
            border: `1px solid ${tagColor}66`,
            borderRadius: 100,
            padding: '4px 14px',
            width: 'fit-content',
          }}
        >
          <div style={{ width: 7, height: 7, borderRadius: '50%', backgroundColor: tagColor }} />
          <span
            style={{
              fontFamily,
              fontSize: 11,
              fontWeight: 700,
              color: tagColor,
              letterSpacing: '3px',
              textTransform: 'uppercase',
            }}
          >
            {tag}
          </span>
        </div>

        {/* Main text */}
        <div
          style={{
            fontFamily,
            fontWeight: 800,
            fontSize: 58,
            color: COLORS.white,
            lineHeight: 1.08,
            letterSpacing: '-1.5px',
            textShadow: '0 2px 40px rgba(0,0,0,0.9)',
            whiteSpace: 'pre-line',
          }}
        >
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
