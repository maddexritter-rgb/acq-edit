import React from 'react';
import { Composition } from 'remotion';
import { Video01Create, TOTAL as T1 } from './compositions/Video01Create';
import { Video02Analyze, TOTAL as T2 } from './compositions/Video02Analyze';
import { Video03Distribute, TOTAL as T3 } from './compositions/Video03Distribute';
import { Video04Compound, TOTAL as T4 } from './compositions/Video04Compound';
import { Video06Highlights, TOTAL as T6 } from './compositions/Video06Highlights';
import { VideoCombined, TOTAL as TC } from './compositions/VideoCombined';
import { FlywheelFilm, TOTAL as TF } from './compositions/FlywheelFilm';
import { FPS, WIDTH, HEIGHT } from './constants';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Video01Create"
      component={Video01Create}
      durationInFrames={T1}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="Video02Analyze"
      component={Video02Analyze}
      durationInFrames={T2}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="Video03Distribute"
      component={Video03Distribute}
      durationInFrames={T3}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="Video04Compound"
      component={Video04Compound}
      durationInFrames={T4}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="Video06Highlights"
      component={Video06Highlights}
      durationInFrames={T6}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="VideoCombined"
      component={VideoCombined}
      durationInFrames={TC}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
    <Composition
      id="FlywheelFilm"
      component={FlywheelFilm}
      durationInFrames={TF}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  </>
);
