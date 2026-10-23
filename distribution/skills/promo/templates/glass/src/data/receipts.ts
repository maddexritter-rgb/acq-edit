// REAL numbers from clip-intel (brand: alex_hormozi), pulled 2026-06-13.
// Public aggregate metrics — safe for a client-facing screen. NO internal revenue.
// Frame as the brand/engine's proven footprint, never as "one prompt produced 4.5B views".

export const GRAND_TOTAL_VIEWS = 4_546_382_511;
export const GRAND_TOTAL_VIEWS_FMT = '4.5B';
export const TOTAL_CLIPS = 29_166;

// Real top clips (public view counts), trimmed captions for on-screen.
export const TOP_CLIPS: { text: string; views: number; viewsFmt: string; platform: string }[] = [
  { text: 'The truth about men vs. women', views: 28_855_360, viewsFmt: '28.8M', platform: 'Instagram' },
  { text: 'Build the right foundation',     views: 9_507_488,  viewsFmt: '9.5M',  platform: 'YouTube' },
  { text: 'When I was single…',              views: 9_059_788,  viewsFmt: '9.0M',  platform: 'YouTube' },
  { text: 'Always be ready',                 views: 8_739_622,  viewsFmt: '8.7M',  platform: 'YouTube' },
  { text: 'Why I quit drinking',             views: 8_628_399,  viewsFmt: '8.6M',  platform: 'Instagram' },
  { text: 'When I lost everything',          views: 8_371_570,  viewsFmt: '8.4M',  platform: 'Instagram' },
  { text: 'Do enough reps to not fail',      views: 7_830_693,  viewsFmt: '7.8M',  platform: 'Instagram' },
];

// Per-platform footprint (real totals)
export const PLATFORMS: { name: string; viewsFmt: string; color: string }[] = [
  { name: 'Instagram', viewsFmt: '1.9B', color: '#e1306c' },
  { name: 'YouTube',   viewsFmt: '765M', color: '#ff0033' },
  { name: 'X',         viewsFmt: '627M', color: '#a08bec' },
  { name: 'TikTok',    viewsFmt: '393M', color: '#25f4ee' },
  { name: 'Facebook',  viewsFmt: '81M',  color: '#2d64e3' },
];
