import React from 'react';
import { AbsoluteFill } from 'remotion';
import { TransitionSeries, linearTiming } from '@remotion/transitions';
import { fade } from '@remotion/transitions/fade';
import { slide } from '@remotion/transitions/slide';
import { GlassBG } from '../components/GlassBG';
import { GlassTitle, GlassOutro } from '../components/GlassBeats';
import { BrandSting } from '../components/BrandSting';
import { NarratorChip } from '../components/CreateShots';
import { RealClipShowcase } from '../components/RealClipShowcase';
import { ChannelScroll } from '../components/ChannelScroll';
import { RawSessionPlayer, L1Prompt, L1Pipeline, HeroClipPlayer, ContentFlywheel, CompoundsBeat, AutoPostScheduler } from '../components/Flywheel';
import { FXOverlay } from '../components/FXOverlay';
import { AudioBed, Sfx } from '../audio';

// THE CONTENT FLYWHEEL — live demo for the L1 Marketing Workshop (drops at "can I show you how we
// do it?"). One live Q&A → AI cuts it → MIDS (long-form) post on the highlights channel + SHORTS
// (9:16) go to Instagram/TikTok/YouTube Shorts → new clients → back to the workshop. AI is the
// accelerant at the cut step. Deck-native language. Order: raw → AI → mids → shorts → the loop.
const STING = 45, HOOK = 92, RAW = 120, PROMPT = 78, PIPE = 128, CHAN = 120, AUTOPOST = 188, HERO = 140,
  GRID = 140, FLY = 200, ESC = 138, OUTRO = 120;
const T = 12;
const DURS = [STING, HOOK, RAW, PROMPT, PIPE, CHAN, AUTOPOST, HERO, GRID, FLY, ESC, OUTRO];
export const TOTAL = DURS.reduce((a, b) => a + b, 0) - T * (DURS.length - 1);

const starts: number[] = [];
DURS.reduce((acc, d, i) => { starts[i] = i === 0 ? 0 : acc; return (i === 0 ? 0 : acc) + d - T; }, 0);
const [, HOOK_AT, RAW_AT, PROMPT_AT, PIPE_AT, CHAN_AT, AUTOPOST_AT, HERO_AT, GRID_AT, FLY_AT, ESC_AT, OUTRO_AT] = starts;

const Wrap: React.FC<{ children: React.ReactNode; caption: string }> = ({ children, caption }) => (
  <AbsoluteFill>{children}<NarratorChip caption={caption} /></AbsoluteFill>
);

export const FlywheelFilm: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: '#0b0c18' }}>
    <GlassBG />
    <TransitionSeries>
      <TransitionSeries.Sequence durationInFrames={STING}><BrandSting /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: T })} />

      <TransitionSeries.Sequence durationInFrames={HOOK}><GlassTitle line1="One Q&A becomes" indigoWord=" a week of content" sub="Watch the content flywheel run — live." /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: 'from-right' })} timing={linearTiming({ durationInFrames: T })} />

      {/* RAW PROOF — the live Q&A AI can't fake */}
      <TransitionSeries.Sequence durationInFrames={RAW}><RawSessionPlayer caption="Every L1 ends with a live Alex Q&A. Real questions, real stakes." /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: T })} />

      {/* THE WORKFLOW — AI is the captain */}
      <TransitionSeries.Sequence durationInFrames={PROMPT}><L1Prompt caption="One operator. One command." /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: T })} />
      <TransitionSeries.Sequence durationInFrames={PIPE}><L1Pipeline caption="Trigger → action → result. No editor." /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: 'from-right' })} timing={linearTiming({ durationInFrames: T })} />

      {/* MIDS — the full answers, long-form, on the highlights channel */}
      <TransitionSeries.Sequence durationInFrames={CHAN}><Wrap caption="The full answers post as mids — long-form on the highlights channel."><ChannelScroll /></Wrap></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: T })} />

      {/* AUTO-POST — the posting runs itself, at volume */}
      <TransitionSeries.Sequence durationInFrames={AUTOPOST}><AutoPostScheduler caption="And the posting runs itself — 15 mids a day, no human touches it." /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: 'from-right' })} timing={linearTiming({ durationInFrames: T })} />

      {/* SHORTS — the sharpest moments, 9:16, to the socials */}
      <TransitionSeries.Sequence durationInFrames={HERO}><HeroClipPlayer clip="l1_sixgyms" title="“Six gyms to zero.”" caption="And the sharpest moments become shorts." /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: 'from-right' })} timing={linearTiming({ durationInFrames: T })} />
      <TransitionSeries.Sequence durationInFrames={GRID}><RealClipShowcase /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: 'from-bottom' })} timing={linearTiming({ durationInFrames: T })} />

      {/* THE FLYWHEEL — the loop + the escalation */}
      <TransitionSeries.Sequence durationInFrames={FLY}><Wrap caption="Each turn powers the next one."><ContentFlywheel /></Wrap></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={slide({ direction: 'from-bottom' })} timing={linearTiming({ durationInFrames: T })} />
      <TransitionSeries.Sequence durationInFrames={ESC}><CompoundsBeat /></TransitionSeries.Sequence>
      <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: T })} />

      {/* PAYOFF */}
      <TransitionSeries.Sequence durationInFrames={OUTRO}><GlassOutro metric="The flywheel is the moat." sub="Build it once. It compounds forever." tagline="Stronger every time it runs" /></TransitionSeries.Sequence>
    </TransitionSeries>

    <FXOverlay grain={0.04} vignette={0} />

    <AudioBed total={TOTAL} />
    <Sfx at={0} name="surge" />
    <Sfx at={12} name="braam" />
    <Sfx at={HOOK_AT} name="whoosh" />
    <Sfx at={RAW_AT - 2} name="whoosh" />
    <Sfx at={PROMPT_AT - 2} name="whoosh" />
    <Sfx at={PIPE_AT - 2} name="whoosh" />
    {[0, 1, 2, 3].map((i) => <Sfx key={i} at={PIPE_AT + 8 + i * 8} name="tick" />)}
    <Sfx at={CHAN_AT - 2} name="whoosh" />
    <Sfx at={AUTOPOST_AT - 2} name="whoosh" />
    {[0, 1, 2, 3, 4].map((i) => <Sfx key={`ap${i}`} at={AUTOPOST_AT + 10 + i * 7} name="tick" volume={0.3} />)}
    <Sfx at={HERO_AT - 2} name="whoosh" />
    <Sfx at={HERO_AT + 4} name="impact" />
    <Sfx at={GRID_AT - 2} name="whoosh" />
    <Sfx at={GRID_AT + 4} name="braam" />
    <Sfx at={FLY_AT - 2} name="whoosh" />
    <Sfx at={FLY_AT + 10} name="riser" />
    <Sfx at={ESC_AT - 2} name="whoosh" />
    <Sfx at={OUTRO_AT - 2} name="whoosh" />
    <Sfx at={OUTRO_AT + 4} name="braam" />
  </AbsoluteFill>
);
