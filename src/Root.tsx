import { Composition, Still } from "remotion";
import { EPISODES } from "./episodes/registry";
import { DEMO, DemoCover } from "./scenes/demo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {Object.values(EPISODES).map((e) => (
        <Composition
          key={e.id}
          id={e.compositionId}
          component={e.component}
          durationInFrames={e.frames}
          fps={e.fps}
          width={1080}
          height={1920}
          defaultProps={{ mix: { music: 1, sfx: 1 } }}
        />
      ))}
      {Object.values(EPISODES).map((e) => (
        <Still key={`${e.id}-cover`} id={e.coverId} component={e.cover} width={1080} height={1920} />
      ))}
      <Composition id="Catalogue-Scenes" component={DEMO.component} durationInFrames={DEMO.frames} fps={30} width={1080} height={1920} defaultProps={{ mix: { music: 1, sfx: 1 } }} />
      <Still id="Catalogue-Cover" component={DemoCover} width={1080} height={1920} />
    </>
  );
};
