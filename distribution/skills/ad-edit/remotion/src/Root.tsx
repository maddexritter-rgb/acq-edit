import React from 'react';
import {Composition} from 'remotion';
import {ReportCard, CARD_W, CARD_H} from './ReportCard';
import {CTAPill, PILL_W, PILL_H, PAD} from './CTAPill';
import {ScalingRoadmapCard, CARD_W as SR_W, CARD_H as SR_H} from './ScalingRoadmapCard';
import {SopFrameworksEndCard, W as SOP_W, H as SOP_H} from './SopFrameworksEndCard';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="ReportCard" component={ReportCard}
      durationInFrames={120} fps={24}
      width={CARD_W + 120} height={CARD_H + 120}
    />
    <Composition
      id="CTAPill" component={CTAPill}
      durationInFrames={144} fps={24}
      width={PILL_W + PAD * 2} height={PILL_H + PAD * 2}
    />
    <Composition
      id="ScalingRoadmapCard" component={ScalingRoadmapCard}
      durationInFrames={96} fps={24}
      width={SR_W + 120} height={SR_H + 120}
    />
    <Composition
      id="SopFrameworksEndCard" component={SopFrameworksEndCard}
      durationInFrames={216} fps={24}
      width={SOP_W} height={SOP_H}
    />
  </>
);
