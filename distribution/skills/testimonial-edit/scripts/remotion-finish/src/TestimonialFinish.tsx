import React from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {loadFont as loadPoppins} from '@remotion/google-fonts/Poppins';

const {fontFamily: poppins} = loadPoppins('normal', {
  weights: ['400', '600', '800'],
});

export type CaptionCard = {text: string; start: number; end: number};

export type FinishProps = {
  videoSrc: string;
  captions: CaptionCard[];
  superLine1: string;
  superLine2: string;
  superOutSec: number;
  disclaimer: string;
  disclaimerOutSec: number;
};

const COLORS = {
  sambucus: '#131628',
  indigo: '#6f00ff',
  lavender: '#a08bec',
};

const GlassChipStyle: React.CSSProperties = {
  background: 'rgba(19, 22, 40, 0.42)',
  WebkitBackdropFilter: 'blur(18px) saturate(1.15)',
  backdropFilter: 'blur(18px) saturate(1.15)',
  border: '1px solid rgba(255,255,255,0.28)',
  borderRadius: 26,
  boxShadow:
    'inset 0 1px 0 rgba(255,255,255,0.25), 0 8px 32px rgba(0,0,0,0.35)',
};

const Caption: React.FC<{card: CaptionCard}> = ({card}) => {
  // No animation (editor note 2026-07-14): hard on, hard off, like short-form.
  const scale = 1;
  const opacity = 1;
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 128,
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          ...GlassChipStyle,
          transform: `scale(${scale})`,
          opacity,
          padding: '18px 44px',
          fontFamily: poppins,
          fontWeight: 600,
          fontSize: 46,
          letterSpacing: 0.5,
          color: 'white',
          textShadow: '0 2px 10px rgba(0,0,0,0.45)',
          whiteSpace: 'nowrap',
        }}
      >
        {card.text}
      </div>
    </div>
  );
};

const SuperChip: React.FC<{
  line1: string;
  line2: string;
  outSec: number;
}> = ({line1, line2, outSec}) => {
  // Plain reference-style super (editor note 2026-07-14): same type language as the
  // question cards — Poppins ExtraBold white with soft shadow, NO glass chip.
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  if (t < 0.8 || t >= outSec) return null;
  return (
    <div
      style={{
        position: 'absolute',
        top: 64,
        left: 80,
        fontFamily: poppins,
      }}
    >
      <div
        style={{
          fontWeight: 800,
          fontSize: 44,
          color: 'white',
          letterSpacing: 1,
          lineHeight: 1.15,
          textShadow: '0 3px 12px rgba(0,0,0,0.6)',
        }}
      >
        {line1}
      </div>
      <div
        style={{
          fontWeight: 800,
          fontSize: 26,
          color: 'white',
          letterSpacing: 1.5,
          marginTop: 4,
          textShadow: '0 2px 10px rgba(0,0,0,0.6)',
        }}
      >
        {line2}
      </div>
    </div>
  );
};

export const TestimonialFinish: React.FC<FinishProps> = ({
  videoSrc,
  captions,
  superLine1,
  superLine2,
  superOutSec,
  disclaimer,
  disclaimerOutSec,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const active = captions.filter((c) => t >= c.start && t < c.end);
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      <OffthreadVideo
        src={videoSrc.startsWith('http') ? videoSrc : staticFile(videoSrc)}
      />
      {active.map((c) => (
        <Caption key={`${c.start}`} card={c} />
      ))}
      <SuperChip line1={superLine1} line2={superLine2} outSec={superOutSec} />
      {disclaimer && t >= 0.5 && t < disclaimerOutSec ? (
        <div
          style={{
            position: 'absolute',
            bottom: 18,
            left: 0,
            right: 0,
            textAlign: 'center',
            fontFamily: poppins,
            fontWeight: 400,
            fontSize: 17,
            color: 'rgba(255,255,255,0.85)',
            textShadow: '0 1px 3px rgba(0,0,0,0.7)',
            padding: '0 160px',
            lineHeight: 1.4,
          }}
        >
          {disclaimer}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
