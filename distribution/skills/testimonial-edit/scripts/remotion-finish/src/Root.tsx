import React from 'react';
import {Composition, getInputProps} from 'remotion';
import {TestimonialFinish, FinishProps} from './TestimonialFinish';

const FPS = 24000 / 1001;

export const Root: React.FC = () => {
  const input = getInputProps() as unknown as FinishProps & {durationInFrames?: number};
  const dur = input.durationInFrames ?? 24 * 60 * 5;
  return (
    <Composition
      id="TestimonialFinish"
      component={TestimonialFinish}
      durationInFrames={Math.round(dur)}
      fps={FPS}
      width={1920}
      height={1080}
      defaultProps={{
        videoSrc: '',
        captions: [],
        superLine1: 'NAME',
        superLine2: 'BUSINESS',
        superOutSec: 12,
        disclaimer: '',
        disclaimerOutSec: 15.5,
      }}
    />
  );
};
