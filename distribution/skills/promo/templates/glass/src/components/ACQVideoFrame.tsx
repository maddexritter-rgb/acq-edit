import React from 'react';
import { AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import { loadFont } from '@remotion/google-fonts/Poppins';
import { COLORS, SPRING_SNAPPY } from '../constants';

const { fontFamily } = loadFont();

interface Props {
  src?: string | null;          // staticFile path to a real recording
  label: string;                // top bar label e.g. "WORKFLOW 01 / CREATE"
  children?: React.ReactNode;    // animated scene to render inside the frame body
}

export const ACQVideoFrame: React.FC<Props> = ({ src, label, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const mountSpring = spring({ frame, fps, config: SPRING_SNAPPY, delay: 0 });
  const scale = interpolate(mountSpring, [0, 1], [0.97, 1]);
  const opacity = mountSpring;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.sambucus, padding: '28px 40px 40px' }}>
      <div
        style={{
          flex: 1,
          borderRadius: 14,
          overflow: 'hidden',
          border: `1px solid rgba(111,0,255,0.28)`,
          boxShadow: [
            `0 0 0 1px rgba(111,0,255,0.10)`,
            `0 0 100px rgba(111,0,255,0.12)`,
            `0 32px 80px rgba(0,0,0,0.6)`,
          ].join(', '),
          display: 'flex',
          flexDirection: 'column',
          transform: `scale(${scale})`,
          opacity,
        }}
      >
        {/* Title bar */}
        <div
          style={{
            height: 46,
            background: COLORS.terminalBar,
            borderBottom: `1px solid rgba(111,0,255,0.18)`,
            display: 'flex',
            alignItems: 'center',
            padding: '0 18px',
            gap: 10,
            flexShrink: 0,
          }}
        >
          {['#ff5f56', '#ffbd2e', '#27c93f'].map((c) => (
            <div key={c} style={{ width: 13, height: 13, borderRadius: '50%', background: c, opacity: 0.85 }} />
          ))}

          <div
            style={{
              marginLeft: 18,
              fontFamily,
              fontSize: 11,
              fontWeight: 600,
              color: `rgba(160,139,236,0.55)`,
              letterSpacing: '3px',
              textTransform: 'uppercase',
            }}
          >
            {label}
          </div>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <div
              style={{
                width: 20, height: 20, borderRadius: 4, background: COLORS.indigo,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <div style={{
                width: 0, height: 0,
                borderLeft: '6px solid transparent',
                borderRight: '6px solid transparent',
                borderBottom: `9px solid white`,
              }} />
            </div>
          </div>
        </div>

        {/* Body: animated scene > real video > placeholder */}
        <div style={{ flex: 1, position: 'relative', background: COLORS.terminalBg, overflow: 'hidden' }}>
          {children ? (
            children
          ) : src ? (
            <OffthreadVideo src={staticFile(src)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <Placeholder />
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Placeholder: React.FC = () => {
  const { fontFamily: pf } = loadFont();
  return (
    <AbsoluteFill style={{
      background: 'linear-gradient(145deg, #0d0e1c 0%, #131628 60%, #0f1025 100%)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20,
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `linear-gradient(rgba(111,0,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(111,0,255,0.04) 1px, transparent 1px)`,
        backgroundSize: '60px 60px',
      }} />
      <div style={{
        width: 80, height: 80, borderRadius: 20,
        background: 'rgba(111,0,255,0.15)', border: '1px solid rgba(111,0,255,0.35)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', zIndex: 1,
      }}>
        <div style={{
          width: 0, height: 0,
          borderTop: '14px solid transparent', borderBottom: '14px solid transparent',
          borderLeft: `22px solid rgba(111,0,255,0.9)`, marginLeft: 6,
        }} />
      </div>
      <div style={{
        fontFamily: pf, fontSize: 13, fontWeight: 600, color: 'rgba(160,139,236,0.4)',
        letterSpacing: '4px', textTransform: 'uppercase', position: 'relative', zIndex: 1,
      }}>
        Drop recording here
      </div>
    </AbsoluteFill>
  );
};
