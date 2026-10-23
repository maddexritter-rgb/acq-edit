import React from 'react';
import { OffthreadVideo, staticFile } from 'remotion';
import { loadFont as loadMono } from '@remotion/google-fonts/JetBrainsMono';
import { GlassPanel } from './GlassPanel';

const { fontFamily: mono } = loadMono();

// A liquid-glass browser frame holding a screen recording. Clean self-made chrome
// (traffic lights + URL pill) so we never show the raw Chrome tabs / automation warning.
export const GlassBrowser: React.FC<{
  src: string;
  urlText: string;
  playbackRate?: number;
  startFrom?: number;
  style?: React.CSSProperties;
}> = ({ src, urlText, playbackRate = 1, startFrom = 0, style }) => {
  return (
    <GlassPanel radius={18} sheen={false} style={{ display: 'flex', flexDirection: 'column', padding: 0, ...style }}>
      {/* chrome */}
      <div style={{
        height: 52, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10, padding: '0 18px',
        borderBottom: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.05)',
      }}>
        {['#ff5f56', '#ffbd2e', '#27c93f'].map((c) => (
          <div key={c} style={{ width: 13, height: 13, borderRadius: '50%', background: c, opacity: 0.9 }} />
        ))}
        <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
          <div style={{
            background: 'rgba(0,0,0,0.28)', border: '1px solid rgba(255,255,255,0.10)', borderRadius: 100,
            padding: '6px 22px', fontFamily: mono, fontSize: 15, color: 'rgba(255,255,255,0.72)',
            display: 'flex', alignItems: 'center', gap: 8, maxWidth: '70%', overflow: 'hidden', whiteSpace: 'nowrap',
          }}>
            <span style={{ opacity: 0.6 }}>🔒</span> {urlText}
          </div>
        </div>
      </div>
      {/* content */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: '#fff' }}>
        <OffthreadVideo
          src={staticFile(src)} playbackRate={playbackRate} startFrom={startFrom} muted
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
        {/* glass glare across the screen */}
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'linear-gradient(120deg, rgba(255,255,255,0.10) 0%, transparent 22%)' }} />
      </div>
    </GlassPanel>
  );
};
