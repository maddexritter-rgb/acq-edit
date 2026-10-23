import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Roboto";

/**
 * ChannelBrowser — a real-looking desktop Chrome window showing a YouTube channel
 * page being SCROLLED by a cursor. Renders with ALPHA (transparent outside the window
 * + soft drop shadow) so it composites as a picture-in-picture "browser pop-up" over a
 * talking-head clip when the speaker names a channel/product.
 *
 * CLIENT-AGNOSTIC: every brand detail is a prop. Pull real assets (avatar/banner/thumbs
 * via yt-dlp + i.ytimg) and pass real titles to make it look authentic.
 *
 * Render with alpha:  Config.setCodec("prores"); Config.setProResProfile("4444");
 *                     Config.setPixelFormat("yuva444p10le");
 * Then ffmpeg overlay it onto the base clip, PTS-shifted to the right beat, y below captions.
 *
 * Worked example (this clip's build): alex/2026-06-16_HighlightsChannelOverlay/10_WORK.
 */

const { fontFamily } = loadFont("normal", {
  weights: ["400", "500", "600", "700"],
  subsets: ["latin"],
  ignoreTooManyRequestsWarning: true,
});

export type ChannelVideo = {
  thumb: string; // staticFile path
  title: string;
  views: string; // e.g. "847"  (rendered as "847 views")
  age: string; // e.g. "3 hours ago"
  dur: string; // e.g. "8:02"
};

export type ChannelBrowserProps = {
  channelName?: string;
  handle?: string; // e.g. "@channel"
  subscribers?: string; // e.g. "85.9K"
  videoCount?: string; // e.g. "1.4K"
  description?: string;
  avatar: string; // staticFile path
  banner: string; // staticFile path
  videos: ChannelVideo[];
  /** url shown in the address bar; defaults to youtube.com/<handle> */
  url?: string;
  /** how far to scroll by the end (px); clamped to content height */
  scrollTo?: number;
};

// window geometry (inside the comp canvas)
const WIN_W = 1328;
const WIN_H = 747;
const CHROME_H = 44;
const MASTHEAD_H = 56;
const VIEWPORT_H = WIN_H - CHROME_H - MASTHEAD_H;
const PAD = 24;
const INNER_W = WIN_W - PAD * 2;
const BANNER_H = Math.round((INNER_W * 351) / 2120);
const COLS = 3;
const GAP = 16;
const CARD_W = Math.round((INNER_W - GAP * (COLS - 1)) / COLS);
const THUMB_H = Math.round((CARD_W * 9) / 16);
const META_H = 80;
const CARD_H = THUMB_H + META_H;
const ROW_GAP = 22;
const HEADER_BLOCK = 212;
const TABS_H = 50;
const CHIPS_H = 46;

const YouTubeLogo: React.FC = () => (
  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
    <svg width="34" height="24" viewBox="0 0 90 64">
      <rect width="90" height="64" rx="16" fill="#FF0000" />
      <path d="M36 18 L66 32 L36 46 Z" fill="#fff" />
    </svg>
    <span style={{ fontSize: 21, fontWeight: 700, letterSpacing: -1.2, color: "#0f0f0f" }}>YouTube</span>
  </div>
);

const VerifiedTick: React.FC = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" style={{ marginLeft: 8, marginTop: 6 }}>
    <circle cx="12" cy="12" r="11" fill="#909090" />
    <path d="M7 12.5 L10.5 16 L17 8.5" stroke="#fff" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const Card: React.FC<{ v: ChannelVideo }> = ({ v }) => (
  <div style={{ width: CARD_W }}>
    <div style={{ width: CARD_W, height: THUMB_H, borderRadius: 12, overflow: "hidden", background: "#000", position: "relative" }}>
      <Img src={staticFile(v.thumb)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      <div style={{ position: "absolute", right: 8, bottom: 8, background: "rgba(0,0,0,0.8)", color: "#fff", fontSize: 12, fontWeight: 600, padding: "1px 5px", borderRadius: 5 }}>
        {v.dur}
      </div>
    </div>
    <div style={{ marginTop: 11, fontSize: 16, fontWeight: 600, lineHeight: "21px", color: "#0f0f0f", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", letterSpacing: -0.1 }}>
      {v.title}
    </div>
    <div style={{ marginTop: 5, fontSize: 14, color: "#606060" }}>
      {v.views} views · {v.age}
    </div>
  </div>
);

const Cursor: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <svg width="26" height="38" viewBox="0 0 26 38" style={{ position: "absolute", left: x, top: y, filter: "drop-shadow(0 2px 3px rgba(0,0,0,0.45))" }}>
    <path d="M2 2 L2 27 L9 20 L13.5 30 L17 28.3 L12.7 18.6 L22 18.6 Z" fill="#fff" stroke="#000" strokeWidth="1.6" strokeLinejoin="round" />
  </svg>
);

export const ChannelBrowser: React.FC<ChannelBrowserProps> = ({
  channelName = "Channel",
  handle = "@channel",
  subscribers = "100K",
  videoCount = "1K",
  description = "New videos every day.",
  avatar,
  banner,
  videos,
  url,
  scrollTo = 2520,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width } = useVideoConfig();

  const rows = Math.ceil(videos.length / COLS);
  const contentH = PAD + BANNER_H + 22 + HEADER_BLOCK + TABS_H + CHIPS_H + 8 + rows * CARD_H + (rows - 1) * ROW_GAP + 48;
  const maxScroll = Math.max(0, contentH - VIEWPORT_H);

  const inS = spring({ frame, fps, config: { damping: 16, mass: 0.7 }, durationInFrames: 18 });
  const outStart = durationInFrames - 18;
  const out = interpolate(frame, [outStart, durationInFrames], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const appear = inS * (1 - out);
  const scale = interpolate(appear, [0, 1], [0.93, 1]);
  const transY = interpolate(appear, [0, 1], [46, 0]) + out * 26;
  const opacity = Math.min(inS, 1 - out);

  const F = [16, 112, 168, 276, 332, 440, 496, 606, 662, 772, 822, outStart];
  const target = Math.min(maxScroll, scrollTo);
  const Y = [0, 360, 360, 760, 760, 1180, 1180, 1620, 1620, 2080, 2080, target].map((y) => Math.min(y, maxScroll));
  const scrollY = interpolate(frame, F, Y, { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.ease) });

  const thumbH = Math.max(46, (VIEWPORT_H * VIEWPORT_H) / contentH);
  const thumbY = maxScroll > 0 ? (scrollY / maxScroll) * (VIEWPORT_H - thumbH) : 0;
  const cx = 690 + 70 * Math.sin(frame / 64) + 30 * Math.sin(frame / 23);
  const cy = 300 + 150 * Math.sin(frame / 88) + 18 * Math.sin(frame / 19);
  const addr = url ?? `youtube.com/${handle}`;
  const winX = (width - WIN_W) / 2;

  return (
    <AbsoluteFill style={{ fontFamily }}>
      <div style={{ position: "absolute", left: winX, top: 40 + transY, width: WIN_W, height: WIN_H, borderRadius: 16, overflow: "hidden", background: "#fff", opacity, transform: `scale(${scale})`, transformOrigin: "center top", boxShadow: "0 50px 110px rgba(0,0,0,0.55), 0 14px 38px rgba(0,0,0,0.42), 0 0 0 1px rgba(0,0,0,0.06)" }}>
        {/* chrome */}
        <div style={{ height: CHROME_H, background: "#f1f3f4", display: "flex", alignItems: "center", padding: "0 14px", gap: 12, borderBottom: "1px solid #e3e5e8" }}>
          <div style={{ display: "flex", gap: 8 }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
              <div key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c }} />
            ))}
          </div>
          <div style={{ display: "flex", gap: 14, color: "#5f6368", fontSize: 16, marginLeft: 6 }}>
            <span>‹</span>
            <span style={{ opacity: 0.4 }}>›</span>
            <span style={{ fontSize: 14 }}>⟳</span>
          </div>
          <div style={{ flex: 1, height: 28, background: "#fff", borderRadius: 14, display: "flex", alignItems: "center", padding: "0 14px", gap: 8, color: "#202124", fontSize: 13.5, border: "1px solid #e3e5e8" }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="#5f6368">
              <path d="M12 1a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2h-1V6a5 5 0 0 0-5-5zm3 8H9V6a3 3 0 0 1 6 0z" />
            </svg>
            <span>{addr}</span>
          </div>
          <div style={{ color: "#5f6368", fontSize: 18, letterSpacing: 1 }}>⋮</div>
        </div>
        {/* masthead */}
        <div style={{ height: MASTHEAD_H, background: "#fff", display: "flex", alignItems: "center", padding: "0 20px", gap: 18, borderBottom: "1px solid #ececec" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ color: "#0f0f0f", fontSize: 19 }}>☰</div>
            <YouTubeLogo />
          </div>
          <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center", gap: 10 }}>
            <div style={{ width: 460, height: 36, border: "1px solid #d3d3d3", borderRadius: "18px 0 0 18px", display: "flex", alignItems: "center", padding: "0 16px", color: "#888", fontSize: 15 }}>Search</div>
            <div style={{ width: 60, height: 38, background: "#f0f0f0", border: "1px solid #d3d3d3", borderLeft: "none", borderRadius: "0 18px 18px 0", display: "flex", alignItems: "center", justifyContent: "center", marginLeft: -10 }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#333" strokeWidth="2">
                <circle cx="11" cy="11" r="7" />
                <line x1="16.5" y1="16.5" x2="21" y2="21" strokeLinecap="round" />
              </svg>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, background: "#f2f2f2", borderRadius: 18, padding: "7px 14px", fontSize: 14, fontWeight: 600, color: "#0f0f0f" }}>
              <span style={{ fontSize: 17, marginTop: -2 }}>＋</span> Create
            </div>
            <div style={{ fontSize: 20 }}>🔔</div>
            <Img src={staticFile(avatar)} style={{ width: 32, height: 32, borderRadius: 16 }} />
          </div>
        </div>
        {/* content */}
        <div style={{ height: VIEWPORT_H, overflow: "hidden", position: "relative", background: "#fff" }}>
          <div style={{ transform: `translateY(${-scrollY}px)`, width: WIN_W }}>
            <div style={{ padding: `${PAD}px ${PAD}px 0` }}>
              <Img src={staticFile(banner)} style={{ width: INNER_W, height: BANNER_H, objectFit: "cover", borderRadius: 12, display: "block" }} />
            </div>
            <div style={{ padding: `22px ${PAD}px 0`, display: "flex", gap: 28, alignItems: "flex-start" }}>
              <Img src={staticFile(avatar)} style={{ width: 158, height: 158, borderRadius: 79 }} />
              <div style={{ paddingTop: 10 }}>
                <div style={{ display: "flex", alignItems: "center" }}>
                  <span style={{ fontSize: 40, fontWeight: 700, color: "#0f0f0f", letterSpacing: -0.5 }}>{channelName}</span>
                  <VerifiedTick />
                </div>
                <div style={{ marginTop: 8, fontSize: 15.5, color: "#0f0f0f", fontWeight: 600 }}>
                  {handle}
                  <span style={{ color: "#606060", fontWeight: 400 }}> · {subscribers} subscribers · {videoCount} videos</span>
                </div>
                <div style={{ marginTop: 6, fontSize: 14.5, color: "#606060", maxWidth: 760 }}>
                  {description} <span style={{ color: "#0f0f0f", fontWeight: 600 }}>...more</span>
                </div>
                <div style={{ marginTop: 16, display: "flex", gap: 10, alignItems: "center" }}>
                  <div style={{ background: "#0f0f0f", color: "#fff", fontSize: 15, fontWeight: 600, padding: "9px 18px", borderRadius: 18 }}>Subscribe</div>
                  <div style={{ background: "#f2f2f2", color: "#0f0f0f", fontSize: 15, fontWeight: 600, padding: "9px 18px", borderRadius: 18 }}>Join</div>
                </div>
              </div>
            </div>
            <div style={{ marginTop: 18, padding: `0 ${PAD}px`, display: "flex", gap: 26, fontSize: 15.5, fontWeight: 600, borderBottom: "1px solid #e5e5e5", height: TABS_H, alignItems: "center" }}>
              {["Home", "Videos", "Shorts", "Live", "Playlists", "Posts"].map((t) => (
                <div key={t} style={{ color: t === "Videos" ? "#0f0f0f" : "#606060", borderBottom: t === "Videos" ? "2px solid #0f0f0f" : "2px solid transparent", height: TABS_H, display: "flex", alignItems: "center" }}>{t}</div>
              ))}
            </div>
            <div style={{ padding: `16px ${PAD}px 0`, display: "flex", gap: 10, height: CHIPS_H }}>
              {["Latest", "Popular", "Oldest"].map((c, i) => (
                <div key={c} style={{ background: i === 0 ? "#0f0f0f" : "#f2f2f2", color: i === 0 ? "#fff" : "#0f0f0f", fontSize: 14, fontWeight: 600, padding: "8px 16px", borderRadius: 9 }}>{c}</div>
              ))}
            </div>
            <div style={{ padding: `8px ${PAD}px 48px`, display: "grid", gridTemplateColumns: `repeat(${COLS}, ${CARD_W}px)`, columnGap: GAP, rowGap: ROW_GAP }}>
              {videos.map((v, i) => (
                <Card key={i} v={v} />
              ))}
            </div>
          </div>
          <div style={{ position: "absolute", top: thumbY, right: 3, width: 7, height: thumbH, background: "rgba(0,0,0,0.28)", borderRadius: 4 }} />
        </div>
        <Cursor x={cx} y={cy} />
      </div>
    </AbsoluteFill>
  );
};
