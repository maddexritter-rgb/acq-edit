import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';

// Subtle cinematic push-in: scales children from `from`→1 over the scene.
// Wrap a scene to give it motion instead of sitting static.
export const CameraPush: React.FC<{
  children: React.ReactNode;
  from?: number;       // starting scale (e.g. 1.06 = slow zoom OUT, 0.96 = push IN)
  delay?: number;
  dur?: number;
  origin?: string;
}> = ({ children, from = 1.05, delay = 0, dur = 90, origin = 'center' }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, durationInFrames: dur, config: { damping: 200, stiffness: 50, mass: 1 } });
  const scale = interpolate(s, [0, 1], [from, 1]);
  return (
    <AbsoluteFill style={{ transform: `scale(${scale})`, transformOrigin: origin }}>
      {children}
    </AbsoluteFill>
  );
};
