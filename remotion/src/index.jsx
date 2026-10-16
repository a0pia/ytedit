import React from "react";
import { Composition, registerRoot } from "remotion";
import { Video } from "./Video.jsx";

const emptyPlan = { fps: 24, width: 720, height: 1280, duration: 2, title: "", brand: "Aopia",
  pack: { frame: "04060B", pop: "2EE6FF", cyber: true }, scenes: [], captions: [], camera: [], brandMark: null, host: null };

const Root = () => (
  <Composition
    id="AopiaVideo"
    component={Video}
    fps={24}
    width={720}
    height={1280}
    durationInFrames={48}
    defaultProps={{ plan: emptyPlan }}
    calculateMetadata={({ props }) => ({
      fps: props.plan.fps,
      durationInFrames: Math.max(1, Math.ceil(props.plan.duration * props.plan.fps)),
    })}
  />
);

registerRoot(Root);
