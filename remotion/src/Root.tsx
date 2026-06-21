import React from "react";
import { Composition } from "remotion";
import { KeystoneVideo } from "./KeystoneVideo";
import { SLIDES, FPS } from "./slides";

const totalFrames = SLIDES.reduce((acc, s) => acc + s.dur, 0);

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Keystone"
      component={KeystoneVideo}
      durationInFrames={totalFrames}
      fps={FPS}
      width={1920}
      height={1080}
    />
  );
};
