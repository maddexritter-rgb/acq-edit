import React from 'react';
import { Audio, Sequence, staticFile, interpolate } from 'remotion';

// Cornfield Chase — start 38s in, where the track is building (his hero/report bed)
export const MUSIC_START = Math.round(38 * 30);

// Everything is rendered with generous headroom; the delivery loudnorm pass
// (I=-14:TP=-1.5) brings final loudness up, so low render levels never clip.
const MASTER = 0.5;

export const AudioBed: React.FC<{ total: number; volume?: number; startFrom?: number }> = ({
  total, volume = 0.2, startFrom = MUSIC_START,
}) => {
  const fadeIn = 24, fadeOut = 50;
  return (
    <Audio
      src={staticFile('audio/music.mp3')}
      startFrom={startFrom}
      volume={(f) => {
        const a = interpolate(f, [0, fadeIn], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        const b = interpolate(f, [total - fadeOut, total], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        return volume * Math.min(a, b);
      }}
    />
  );
};

type SfxName = 'whoosh' | 'tick' | 'shimmer' | 'impact' | 'riser' | 'surge' | 'braam';
const VOL: Record<SfxName, number> = {
  whoosh: 0.55, tick: 0.42, shimmer: 0.6, impact: 0.62, riser: 0.5, surge: 0.5, braam: 0.7,
};

export const Sfx: React.FC<{ at: number; name: SfxName; volume?: number }> = ({ at, name, volume }) => {
  const v = (volume ?? VOL[name] ?? 0.5) * MASTER;
  return (
    <Sequence from={at} durationInFrames={5 * 30} layout="none">
      <Audio src={staticFile(`audio/${name}.mp3`)} volume={Math.min(v, 0.85)} />
    </Sequence>
  );
};
