import React from 'react';

// Frosted "liquid glass" panel — backdrop-blurs whatever GlassBG sits behind it,
// with a light top edge, inner specular highlight, soft depth shadow, and a diagonal sheen.
export const GlassPanel: React.FC<{
  children?: React.ReactNode;
  style?: React.CSSProperties;
  radius?: number;
  blur?: number;
  sheen?: boolean;
  tint?: number; // 0..1 fill strength
  dark?: boolean; // dark frosted fill — use when content/text sits on top for readability
}> = ({ children, style, radius = 22, blur = 24, sheen = true, tint = 1, dark = false }) => {
  return (
    <div style={{
      position: 'relative',
      background: dark
        ? `linear-gradient(135deg, rgba(16,18,34,${0.86 * tint}), rgba(12,13,26,${0.66 * tint}))`
        : `linear-gradient(135deg, rgba(255,255,255,${0.11 * tint}), rgba(255,255,255,${0.03 * tint}))`,
      backdropFilter: `blur(${blur}px) saturate(1.35)`,
      WebkitBackdropFilter: `blur(${blur}px) saturate(1.35)`,
      border: dark ? '1px solid rgba(160,139,236,0.28)' : '1px solid rgba(255,255,255,0.20)',
      borderRadius: radius,
      boxShadow: [
        '0 36px 90px rgba(0,0,0,0.5)',
        '0 2px 10px rgba(0,0,0,0.3)',
        'inset 0 1px 0 rgba(255,255,255,0.4)',
        'inset 0 -1px 0 rgba(255,255,255,0.06)',
        'inset 0 0 60px rgba(111,0,255,0.06)',
      ].join(', '),
      overflow: 'hidden',
      ...style,
    }}>
      {sheen && (
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'linear-gradient(118deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.02) 30%, transparent 55%)',
        }} />
      )}
      {children}
    </div>
  );
};
