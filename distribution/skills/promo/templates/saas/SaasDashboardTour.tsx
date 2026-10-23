/**
 * SaaS-style 3D dashboard tour with animated cursor.
 * Port of AE "3D Interactive Course Tour" (Scene 3 in editing-styles/saas-animation-style.md).
 *
 * Shows a grid of product tiles in 3D space, with an animated cursor that hovers
 * over each tile, triggering hover-scale + tilt interactions. Camera slowly
 * pushes in for dimensionality.
 *
 * Usage:
 *   <Composition
 *     id="saas-dashboard-tour"
 *     component={SaasDashboardTour}
 *     durationInFrames={240}
 *     fps={30}
 *     width={1080}
 *     height={1920}
 *     defaultProps={{
 *       title: "Your dashboard",
 *       tiles: [
 *         {title: "Analytics", color: "#8b5cf6"},
 *         {title: "Reports", color: "#ec4899"},
 *         {title: "Settings", color: "#f59e0b"},
 *         {title: "Team", color: "#10b981"},
 *         {title: "Integrations", color: "#3b82f6"},
 *         {title: "Billing", color: "#ef4444"}
 *       ],
 *       brand: {primary: "#8b5cf6", accent: "#ec4899"}
 *     }}
 *   />
 */

import React from "react";
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";

export type DashboardTile = {
  title: string;
  color: string;
};

export type SaasDashboardTourProps = {
  title: string;
  tiles: DashboardTile[];
  brand: {primary: string; accent: string};
};

// Calculate tile positions in a 2×N grid
const getTileLayout = (count: number) => {
  const cols = 2;
  const rows = Math.ceil(count / cols);
  return {cols, rows};
};

const DashboardTile: React.FC<{
  tile: DashboardTile;
  col: number;
  row: number;
  totalCols: number;
  cursorHoverFrame: number | null;
  entryStartFrame: number;
}> = ({tile, col, row, cursorHoverFrame, entryStartFrame}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Entry animation
  const entryLocal = frame - entryStartFrame;
  const entry = spring({frame: entryLocal, fps, config: {damping: 10, mass: 0.7, stiffness: 90}});
  const entryScale = interpolate(entry, [0, 1], [0, 1]);
  const entryY = interpolate(entry, [0, 1], [80, 0]);
  const entryOpacity = interpolate(entryLocal, [0, 10], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});

  // Hover interaction — when cursor is on this tile
  const hoverProgress =
    cursorHoverFrame !== null
      ? spring({frame: frame - cursorHoverFrame, fps, config: {damping: 10, mass: 0.5, stiffness: 120}})
      : 0;
  const hoverBounce =
    cursorHoverFrame !== null && frame > cursorHoverFrame + 15
      ? spring({frame: frame - (cursorHoverFrame + 15), fps, config: {damping: 12, mass: 0.4, stiffness: 100}})
      : 1;
  const hoverScale = 1 + hoverProgress * 0.08 * (1 - Math.max(0, hoverBounce - 0.5) * 0.5);
  const hoverTiltY = interpolate(hoverProgress, [0, 0.5, 1], [0, 15, 8]);

  const finalScale = entryScale * hoverScale;

  return (
    <div
      style={{
        width: 420,
        height: 260,
        borderRadius: 36,
        background: `linear-gradient(135deg, ${tile.color}ee 0%, ${tile.color}bb 100%)`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "Inter, system-ui, sans-serif",
        fontSize: 52,
        fontWeight: 800,
        color: "white",
        letterSpacing: "-1.5px",
        transform: `translateY(${entryY}px) scale(${finalScale}) rotateY(${hoverTiltY}deg)`,
        transformStyle: "preserve-3d",
        opacity: entryOpacity,
        boxShadow: `
          0 20px 60px ${tile.color}55,
          inset 0 0 40px rgba(255,255,255,0.15)
        `,
        transition: "none",
      }}
    >
      {tile.title}
    </div>
  );
};

const Cursor: React.FC<{
  waypoints: {x: number; y: number; frame: number}[];
  brand: {primary: string; accent: string};
}> = ({waypoints}) => {
  const frame = useCurrentFrame();
  // Find current segment
  let segStart = waypoints[0];
  let segEnd = waypoints[0];
  for (let i = 1; i < waypoints.length; i++) {
    if (frame < waypoints[i].frame) {
      segStart = waypoints[i - 1];
      segEnd = waypoints[i];
      break;
    }
    segStart = waypoints[i];
    segEnd = waypoints[i];
  }
  const t =
    segEnd.frame === segStart.frame
      ? 1
      : (frame - segStart.frame) / (segEnd.frame - segStart.frame);
  const eased = t < 0 ? 0 : t > 1 ? 1 : t * t * (3 - 2 * t); // smoothstep
  const x = segStart.x + (segEnd.x - segStart.x) * eased;
  const y = segStart.y + (segEnd.y - segStart.y) * eased;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        fontSize: 80,
        transform: "rotateY(4deg) rotateX(-7deg)",
        transformStyle: "preserve-3d",
        filter: "drop-shadow(0 11px 8px rgba(40,40,40,0.45))",
        zIndex: 100,
        pointerEvents: "none",
        transition: "none",
      }}
    >
      👆
    </div>
  );
};

export const SaasDashboardTour: React.FC<SaasDashboardTourProps> = ({title, tiles, brand}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames, width, height} = useVideoConfig();

  const {cols, rows} = getTileLayout(tiles.length);

  // Tile grid geometry
  const gap = 36;
  const tileW = 420;
  const tileH = 260;
  const gridW = cols * tileW + (cols - 1) * gap;
  const gridH = rows * tileH + (rows - 1) * gap;
  const originX = (width - gridW) / 2;
  const originY = (height - gridH) / 2 + 80; // offset below title

  // Cursor waypoints — center of each tile, with entry + exit offscreen
  const cursorWaypoints = [
    {x: width + 100, y: height / 2, frame: 0},                 // offscreen right
    {x: width + 100, y: height / 2, frame: 90},                // wait for tiles to enter
    ...tiles.map((_, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      return {
        x: originX + col * (tileW + gap) + tileW / 2 - 40,
        y: originY + row * (tileH + gap) + tileH / 2 - 40,
        frame: 110 + i * 22,
      };
    }),
    {x: -100, y: height / 2, frame: durationInFrames},         // exit left
  ];

  // For each tile, figure out when the cursor hovers it
  const getHoverFrame = (i: number) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    return 110 + i * 22;
  };

  // Camera push-in (CSS scale on whole scene)
  const cameraScale = interpolate(frame, [0, durationInFrames], [1.0, 1.08], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cameraYShift = interpolate(frame, [0, durationInFrames], [0, -30]);

  // Title fade in
  const titleProgress = spring({frame, fps, config: {damping: 12, mass: 0.6, stiffness: 90}});
  const titleOpacity = interpolate(titleProgress, [0, 1], [0, 1]);
  const titleY = interpolate(titleProgress, [0, 1], [-40, 0]);

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at 50% 40%, ${brand.primary}22 0%, #f5f5f5 70%, #eee 100%)`,
        perspective: 1200,
      }}
    >
      <AbsoluteFill style={{transform: `scale(${cameraScale}) translateY(${cameraYShift}px)`, transformOrigin: "center"}}>
        {/* Title */}
        <div
          style={{
            position: "absolute",
            top: 160,
            left: 0,
            right: 0,
            textAlign: "center",
            fontSize: 96,
            fontWeight: 900,
            fontFamily: "Inter, system-ui, sans-serif",
            color: "#1a1a1a",
            letterSpacing: "-3px",
            opacity: titleOpacity,
            transform: `translateY(${titleY}px)`,
          }}
        >
          {title}
        </div>

        {/* Tile grid */}
        <div
          style={{
            position: "absolute",
            top: originY,
            left: originX,
            display: "grid",
            gridTemplateColumns: `repeat(${cols}, ${tileW}px)`,
            gap,
            transformStyle: "preserve-3d",
          }}
        >
          {tiles.map((tile, i) => {
            const col = i % cols;
            const row = Math.floor(i / cols);
            return (
              <DashboardTile
                key={i}
                tile={tile}
                col={col}
                row={row}
                totalCols={cols}
                cursorHoverFrame={frame >= getHoverFrame(i) ? getHoverFrame(i) : null}
                entryStartFrame={20 + i * 8}
              />
            );
          })}
        </div>

        <Cursor waypoints={cursorWaypoints} brand={brand} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
