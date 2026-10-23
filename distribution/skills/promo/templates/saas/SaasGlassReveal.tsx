/**
 * SaaS-style glass-UI card reveal.
 * Port of AE "Glass UI Card Reveal" (Scene 2 in editing-styles/saas-animation-style.md).
 *
 * Shows N cards that slide in from the sides with glass/backdrop-blur effect.
 * Each card has an icon + label and animates in sequence.
 *
 * Usage:
 *   <Composition
 *     id="saas-glass-reveal"
 *     component={SaasGlassReveal}
 *     durationInFrames={180}
 *     fps={30}
 *     width={1080}
 *     height={1920}
 *     defaultProps={{
 *       heading: "Three ways to win",
 *       cards: [
 *         {icon: "⚡", label: "fastest"},
 *         {icon: "✨", label: "easiest"},
 *         {icon: "🎯", label: "smartest"}
 *       ],
 *       brand: {primary: "#8b5cf6", accent: "#ec4899"}
 *     }}
 *   />
 */

import React from "react";
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";

export type GlassCardData = {
  icon: string;    // emoji or (TODO) image URL
  label: string;
};

export type SaasGlassRevealProps = {
  heading: string;
  cards: GlassCardData[];
  brand: {
    primary: string;
    accent: string;
  };
};

const BlurredBackdrop: React.FC<{primary: string; accent: string}> = ({primary, accent}) => (
  <AbsoluteFill
    style={{
      background: `
        radial-gradient(circle at 20% 30%, ${primary}55 0%, transparent 50%),
        radial-gradient(circle at 80% 70%, ${accent}55 0%, transparent 50%),
        linear-gradient(180deg, #fafafa 0%, #f0f0f0 100%)
      `,
    }}
  />
);

const GlassCard: React.FC<{
  card: GlassCardData;
  index: number;
  startFrame: number;
  fromLeft: boolean;
  brand: {primary: string; accent: string};
}> = ({card, index, startFrame, fromLeft, brand}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const localFrame = frame - startFrame;

  // Bouncy slide-in from side
  const slideProgress = spring({frame: localFrame, fps, config: {damping: 10, mass: 0.8, stiffness: 80}});
  const xOffset = interpolate(slideProgress, [0, 1], [fromLeft ? -600 : 600, 0]);
  const rotation = interpolate(slideProgress, [0, 1], [fromLeft ? -8 : 8, 0]);
  const opacity = interpolate(localFrame, [0, 10], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});

  // Icon bounce (slight delay)
  const iconProgress = spring({frame: localFrame - 6, fps, config: {damping: 7, mass: 0.5, stiffness: 100}});
  const iconScale = interpolate(iconProgress, [0, 1], [0, 1]);

  // Label bounce
  const labelProgress = spring({frame: localFrame - 10, fps, config: {damping: 9, mass: 0.6, stiffness: 90}});
  const labelScale = interpolate(labelProgress, [0, 1], [0, 1]);

  return (
    <div
      style={{
        width: 400,
        height: 280,
        borderRadius: 44,
        opacity,
        transform: `translateX(${xOffset}px) rotate(${rotation}deg)`,
        background: `linear-gradient(135deg,
          rgba(255,255,255,0.75) 0%,
          ${brand.primary}22 40%,
          ${brand.accent}22 70%,
          rgba(255,255,255,0.55) 100%)`,
        backdropFilter: "blur(30px)",
        border: "2px solid rgba(255,255,255,0.6)",
        boxShadow: `
          0 15px 45px rgba(0,0,0,0.07),
          inset 0 0 60px rgba(255,255,255,0.25)
        `,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 24,
        padding: "0 36px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* CC Light Sweep approximation — diagonal gradient that moves across */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: `${interpolate(localFrame, [20, 60], [-100, 200], {extrapolateRight: "clamp"})}%`,
          width: "50%",
          height: "100%",
          background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)",
          transform: "skewX(-15deg)",
          pointerEvents: "none",
        }}
      />
      <div style={{fontSize: 120, transform: `scale(${iconScale})`, filter: `drop-shadow(0 0 16px ${brand.primary}66)`}}>
        {card.icon}
      </div>
      <div
        style={{
          fontSize: 64,
          fontWeight: 900,
          fontFamily: "Inter, system-ui, sans-serif",
          background: `linear-gradient(135deg, ${brand.primary} 0%, ${brand.accent} 100%)`,
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          letterSpacing: "-2px",
          transform: `scale(${labelScale})`,
        }}
      >
        {card.label}
      </div>
    </div>
  );
};

export const SaasGlassReveal: React.FC<SaasGlassRevealProps> = ({heading, cards, brand}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const headingProgress = spring({frame, fps, config: {damping: 12, mass: 0.6, stiffness: 90}});
  const headingY = interpolate(headingProgress, [0, 1], [-60, 0]);
  const headingOpacity = interpolate(headingProgress, [0, 1], [0, 1]);

  return (
    <AbsoluteFill>
      <BlurredBackdrop primary={brand.primary} accent={brand.accent} />

      <AbsoluteFill style={{alignItems: "center", justifyContent: "center", gap: 60}}>
        <div
          style={{
            fontSize: 96,
            fontWeight: 900,
            fontFamily: "Inter, system-ui, sans-serif",
            color: "#1a1a1a",
            letterSpacing: "-2px",
            transform: `translateY(${headingY}px)`,
            opacity: headingOpacity,
            textAlign: "center",
          }}
        >
          {heading}
        </div>

        <div style={{display: "flex", flexDirection: "column", gap: 36}}>
          {cards.map((card, i) => (
            <GlassCard
              key={i}
              card={card}
              index={i}
              startFrame={20 + i * 25}
              fromLeft={i % 2 === 0}
              brand={brand}
            />
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
