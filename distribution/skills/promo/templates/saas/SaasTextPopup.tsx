/**
 * SaaS-style text pop-up scene.
 * Port of the After Effects "Minimal Text Pop-Up" scene described in
 * editing-styles/saas-animation-style.md (Scene 1).
 *
 * Usage in Root.tsx:
 *   <Composition
 *     id="saas-text-popup"
 *     component={SaasTextPopup}
 *     durationInFrames={120}
 *     fps={30}
 *     width={1080}
 *     height={1920}
 *     defaultProps={{title: "This is", accent: "ACME", suffix: "2.0", brand: {primary: "#8b5cf6", accent: "#ec4899"}}}
 *   />
 */

import React from "react";
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";

export type SaasTextPopupProps = {
  /** Pre-title word (e.g. "This is") */
  title: string;
  /** Main brand/product name (e.g. "ACME") */
  accent: string;
  /** Optional version suffix (e.g. "2.0") */
  suffix?: string;
  brand: {
    primary: string;   // main brand color — used for backdrop blobs + text accent
    accent: string;    // secondary color — used for gradient variation
  };
  /** Optional logo path (public/) — if omitted, renders a rounded-rect placeholder */
  logoPath?: string;
};

// Animated gradient backdrop with 3 blurred pastel blobs (Scene-1 background)
const SaasBackdrop: React.FC<{primary: string; accent: string}> = ({primary, accent}) => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame, [0, 120], [0, 40]);
  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(180deg, #ffffff 0%, #f3f3f3 100%)",
        overflow: "hidden",
      }}
    >
      {/* Blob 1 — primary color, soft, drifting */}
      <div
        style={{
          position: "absolute",
          width: 900,
          height: 900,
          borderRadius: "50%",
          background: primary,
          opacity: 0.5,
          filter: "blur(180px)",
          top: -200 + drift,
          left: -150 - drift,
        }}
      />
      {/* Blob 2 — accent color, opposite corner */}
      <div
        style={{
          position: "absolute",
          width: 800,
          height: 800,
          borderRadius: "50%",
          background: accent,
          opacity: 0.3,
          filter: "blur(200px)",
          bottom: -180 + drift,
          right: -100 - drift,
        }}
      />
      {/* Blob 3 — mid, darker variant */}
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: primary,
          opacity: 0.35,
          filter: "blur(140px)",
          top: "40%",
          left: "30%",
        }}
      />
    </AbsoluteFill>
  );
};

// Word-by-word pop-in. AE equivalent: Animator Position + Blur + Opacity + Fill color with word stagger.
const PopInText: React.FC<{
  text: string;
  startFrame: number;
  fontSize: number;
  fontWeight: number;
  color: string;
  accentColor?: string;
  letterSpacing?: string;
}> = ({text, startFrame, fontSize, fontWeight, color, accentColor, letterSpacing}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = text.split(" ");

  return (
    <div style={{display: "flex", justifyContent: "center", gap: 24}}>
      {words.map((word, i) => {
        const wordStart = startFrame + i * 3; // 100ms stagger per word (3 frames @ 30fps)
        const localFrame = frame - wordStart;
        const progress = spring({frame: localFrame, fps, config: {damping: 12, mass: 0.6, stiffness: 120}});
        const opacity = interpolate(progress, [0, 1], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
        const y = interpolate(progress, [0, 1], [40, 0]);
        const blur = interpolate(progress, [0, 1], [10, 0]);
        const tint = interpolate(progress, [0, 1], [1, 0]);
        const finalColor = accentColor ? `color-mix(in srgb, ${accentColor} ${tint * 100}%, ${color})` : color;
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              fontSize,
              fontWeight,
              letterSpacing,
              color: finalColor,
              opacity,
              transform: `translateY(${y}px)`,
              filter: `blur(${blur}px)`,
              fontFamily: "Inter, system-ui, sans-serif",
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};

// Icon/logo pop-in with bounce (scale 0→100, rotation -720→0, inner-glow effect)
const LogoPopIn: React.FC<{startFrame: number; logoPath?: string; primary: string}> = ({
  startFrame,
  logoPath,
  primary,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const localFrame = frame - startFrame;
  const scale = spring({frame: localFrame, fps, config: {damping: 8, mass: 0.8, stiffness: 90}});
  const rotation = interpolate(localFrame, [0, 30], [-360, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: 280,
        height: 280,
        borderRadius: 56,
        background: "#ffffff",
        boxShadow: `
          0 17px 40px rgba(0,0,0,0.15),
          inset 0 0 90px rgba(255,255,255,0.6)
        `,
        border: `3px solid ${primary}22`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transform: `scale(${scale}) rotate(${rotation}deg)`,
      }}
    >
      {logoPath ? (
        <img src={logoPath} style={{width: "70%", height: "70%", objectFit: "contain"}} />
      ) : (
        <div style={{fontSize: 140, fontWeight: 900, color: primary, fontFamily: "Inter"}}>★</div>
      )}
    </div>
  );
};

export const SaasTextPopup: React.FC<SaasTextPopupProps> = ({title, accent, suffix, brand, logoPath}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  // Transition-out: scale grows to fill frame in final 15 frames
  const exitProgress = Math.max(0, frame - (durationInFrames - 15)) / 15;
  const exitScale = interpolate(exitProgress, [0, 1], [1, 8]);
  const exitOpacity = interpolate(exitProgress, [0.7, 1], [1, 0]);

  return (
    <AbsoluteFill
      style={{transform: `scale(${exitScale})`, opacity: exitOpacity, transformOrigin: "center"}}
    >
      <SaasBackdrop primary={brand.primary} accent={brand.accent} />

      <AbsoluteFill style={{alignItems: "center", justifyContent: "center", gap: 40}}>
        <PopInText
          text={title}
          startFrame={10}
          fontSize={110}
          fontWeight={500}
          color="#1a1a1a"
          accentColor={brand.primary}
        />
        <LogoPopIn startFrame={40} logoPath={logoPath} primary={brand.primary} />
        <div style={{display: "flex", alignItems: "baseline", gap: 16}}>
          <PopInText
            text={accent}
            startFrame={60}
            fontSize={160}
            fontWeight={900}
            color={brand.primary}
            letterSpacing="-3px"
          />
          {suffix && (
            <PopInText
              text={suffix}
              startFrame={75}
              fontSize={80}
              fontWeight={900}
              color={brand.accent}
              letterSpacing="-2px"
            />
          )}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
