// Aopia / Hype Studio video composition. The Python side (app/capsule.py) plans
// everything - scenes, palettes, caption timing, typography-map camera moments,
// brand mark and the host's per-frame rig - and this file only draws it.
import React from "react";
import { AbsoluteFill, Easing, Img, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/space-grotesk/500.css";
import "@fontsource/space-grotesk/700.css";

const HEAD = "'Space Grotesk', 'Inter', sans-serif";
const BODY = "'Inter', 'Space Grotesk', sans-serif";
const TIMELINE_Y = 236;
const CAPTION_Y = 1128;
const RED = "#E8735A";
const GREEN = "#9CCB5A";
const hex = (value) => `#${value}`;

const clamp = (value) => Math.min(1, Math.max(0, value));
const ease = Easing.out(Easing.cubic);
// Progress of an entrance that starts `delay` seconds into a sequence and lasts `ms`.
const enter = (frame, fps, delay, ms) => ease(clamp((frame / fps - delay) / (ms / 1000)));
const smooth = (x) => x * x * (3 - 2 * x);

const Abs = ({ x = 0, y = 0, w, h, style, children }) => (
  <div style={{ position: "absolute", left: x, top: y, width: w, height: h, ...style }}>{children}</div>
);

// --- world pieces -------------------------------------------------------------------

const Grid = ({ ink }) => (
  <svg width={720} height={1280} style={{ position: "absolute", left: 0, top: 0 }}>
    {Array.from({ length: 9 }, (_, i) => (
      <rect key={`v${i}`} x={40 + i * 80} y={0} width={1} height={1280} fill={hex(ink)} opacity={0.08} />
    ))}
    {Array.from({ length: 13 }, (_, i) => (
      <rect key={`h${i}`} x={0} y={300 + i * 80} width={720} height={1} fill={hex(ink)} opacity={0.08} />
    ))}
  </svg>
);

const Timeline = ({ pal, frame, fps, brandPill }) => {
  const draw = enter(frame, fps, 0, 520);
  const pop = spring({ frame, fps, config: { damping: 11, stiffness: 160 } });
  return (
    <>
      <Abs x={0} y={TIMELINE_Y - 1} w={360} h={2} style={{ background: RED, opacity: 0.75 }} />
      <Abs x={360} y={TIMELINE_Y - 1} w={360} h={2} style={{ background: GREEN, opacity: 0.75 }} />
      <Abs x={128} y={TIMELINE_Y - 1} w={512 * draw} h={3} style={{ background: hex(pal.ink), opacity: 0.45 }} />
      <Abs x={64} y={TIMELINE_Y - 32} w={64} h={64}
        style={{ borderRadius: 32, background: hex(pal.accent), transform: `scale(${pop})`,
                 boxShadow: `0 0 18px ${hex(pal.accent)}66`, display: "grid", placeItems: "center" }}>
        <svg width={18} height={18} viewBox="-9 -9 18 18">
          <path d="M -9 -9 L 9 -9 L 9 -5 L -9 -5 Z M -9 -2 L 9 -2 L 9 2 L -9 2 Z M -9 5 L 4 5 L 4 9 L -9 9 Z" fill={hex(pal.on_accent)} />
        </svg>
      </Abs>
      <Abs x={610} y={TIMELINE_Y - 30} w={60} h={60}
        style={{ borderRadius: 30, background: hex(pal.ink), display: "grid", placeItems: "center",
                 color: hex(pal.panel), fontSize: 30, fontFamily: HEAD, fontWeight: 700 }}>+</Abs>
      {brandPill}
    </>
  );
};

const Lines = ({ text, size, color, x, y, w, frame, fps, delay = 0, align = "left", italic = false, weight = 500 }) => {
  const p = enter(frame, fps, delay, 340);
  return (
    <Abs x={x} y={y + 30 * (1 - p)} w={w}
      style={{ opacity: p, color: hex(color), fontFamily: HEAD, fontWeight: weight, fontSize: size, lineHeight: 1.16,
               whiteSpace: "pre-line", textAlign: align, fontStyle: italic ? "italic" : "normal", letterSpacing: -0.5 }}>
      {text}
    </Abs>
  );
};

const Label = ({ text, x, y, color, frame, fps, size = 19, opacity = 0.8 }) => (
  <Abs x={x} y={y} style={{ color: hex(color), fontFamily: BODY, fontSize: size, fontWeight: 500, letterSpacing: 0.4,
                             opacity: opacity * enter(frame, fps, 0, 160) }}>{text}</Abs>
);

const Card = ({ x, y, w, h, pal, frame, fps, delay = 0, children, border = true }) => {
  const p = enter(frame, fps, delay, 320);
  return (
    <Abs x={x} y={y + 42 * (1 - p)} w={w} h={h}
      style={{ opacity: p, borderRadius: 36, background: hex(pal.card),
               border: border ? `1.5px solid ${hex(pal.accent)}44` : "none",
               boxShadow: "0 18px 40px rgba(0,0,0,0.25)", overflow: "hidden" }}>
      {children}
    </Abs>
  );
};

const Wave = ({ pal, frame, fps, length }) => {
  const shift = (frame / fps) / Math.max(0.1, length);
  const wave = (amplitude, period, phase, base) => {
    let d = "M 0 100";
    for (let x = 0; x <= 1400; x += 20) d += ` L ${x} ${base + amplitude * Math.sin(x / period + phase)}`;
    return `${d} L 1400 100 Z`;
  };
  return (
    <svg width={640} height={100} style={{ position: "absolute", left: 0, bottom: 0 }}>
      <path d={wave(16, 60, 0, 30)} fill={hex(pal.accent)} transform={`translate(${-680 + 680 * shift} 0)`} />
      <path d={wave(12, 44, 1.3, 56)} fill="#A9A7A0" opacity={0.75} transform={`translate(${-640 * shift} 0)`} />
    </svg>
  );
};

const BrandMark = ({ mark, hero, pal, frame, fps }) => {
  if (!mark) return null;
  const pop = spring({ frame, fps, config: { damping: 12 } });
  if (mark.logo) {
    const size = hero ? 150 : 72;
    const [x, y] = hero ? [66, 516] : [604, 200];
    return (
      <Abs x={x} y={y} w={size} h={size}
        style={{ background: "#FFFFFF", borderRadius: size / 4, transform: `scale(${pop})`, display: "grid",
                 placeItems: "center", boxShadow: "0 10px 30px rgba(0,0,0,.3)" }}>
        <Img src={mark.logo} style={{ width: size * 0.76, height: size * 0.76, objectFit: "contain" }} />
      </Abs>
    );
  }
  const size = hero ? 34 : 22;
  return (
    <Abs x={hero ? 66 : undefined} y={hero ? 520 : TIMELINE_Y - size * 0.85}
      style={{ right: hero ? undefined : 116, background: hex(pal.accent), color: hex(pal.on_accent),
               fontFamily: HEAD, fontWeight: 700, fontSize: size, padding: `${size * 0.32}px ${size * 0.8}px`,
               borderRadius: 999, transform: `scaleY(${pop})`, boxShadow: `0 0 20px ${hex(pal.accent)}55` }}>
      {mark.name}
    </Abs>
  );
};

// Back layer of a scene: everything under the host.
const SceneBack = ({ scene, plan }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pal = scene.palette;
  const length = scene.end - scene.start;
  const host = plan.host && scene.host;
  const content = [];
  if (host === "big") {
    const p = enter(frame, fps, 0, 360);
    content.push(
      <Abs key="stage" x={40} y={500 + 40 * (1 - p)} w={640} h={430}
        style={{ borderRadius: 40, background: hex(pal.deep), opacity: p }} />,
      <Abs key="halo" x={190} y={550} w={340} h={340}
        style={{ borderRadius: 170, background: `radial-gradient(circle, ${hex(pal.accent)}55, ${hex(pal.accent)}00 70%)`,
                 transform: `scale(${0.6 + 0.4 * enter(frame, fps, 0, 420)})` }} />,
    );
  } else if (host === "pip" && !scene.roaming) {
    const [cx, cy, r] = plan.host.pip;
    const pop = spring({ frame, fps, config: { damping: 13 } });
    content.push(
      <Abs key="pip" x={cx - r} y={cy - r} w={r * 2} h={r * 2}
        style={{ borderRadius: r, background: hex(pal.deep), transform: `scale(${pop})` }} />,
    );
  }

  const L = scene.layout;
  if (L === "hook") {
    content.push(<Label key="l" text="Bugünün konusu" x={62} y={268} color={pal.soft} frame={frame} fps={fps} />);
    scene.text.split("\n").forEach((line, i) =>
      content.push(<Lines key={`t${i}`} text={line} size={scene.size} color={pal.ink} x={62}
        y={300 + i * Math.round(scene.size * 1.12)} w={620} frame={frame} fps={fps} delay={Math.min(0.1 * i, length * 0.15)} />));
  } else if (L === "editorial") {
    content.push(
      <Card key="c" x={40} y={300} w={640} h={410} pal={pal} frame={frame} fps={fps}>
        <Label text="Odak noktası" x={36} y={30} color={pal.card_ink} frame={frame} fps={fps} size={18} opacity={0.6} />
        <Abs x={566} y={22} w={52} h={52} style={{ borderRadius: 26, background: "#FFFFFF", display: "grid", placeItems: "center" }}>
          <div style={{ width: 16, height: 16, borderRadius: 8, background: hex(pal.accent) }} />
        </Abs>
        <Lines text={scene.text} size={scene.size} color={pal.card_ink} x={36} y={78} w={560} frame={frame} fps={fps} delay={0.08} />
        <Wave pal={pal} frame={frame} fps={fps} length={length} />
      </Card>,
    );
  } else if (L === "card") {
    const p = enter(frame, fps, 0, 320);
    content.push(
      <Abs key="pill" x={40 - 300 * (1 - p)} y={290} w={300} h={64}
        style={{ borderRadius: 32, background: hex(pal.accent), display: "flex", alignItems: "center", gap: 18,
                 color: hex(pal.on_accent), fontFamily: HEAD, fontWeight: 700, fontSize: 21, paddingLeft: 8 }}>
        <div style={{ width: 48, height: 48, borderRadius: 24, background: hex(pal.on_accent) }} />Gündemde
      </Abs>,
      <Abs key="link" x={190} y={354} w={2} h={34} style={{ background: hex(pal.ink), opacity: 0.4 }} />,
      <Card key="c" x={40} y={388} w={640} h={330} pal={pal} frame={frame} fps={fps}>
        <Lines text={scene.text} size={scene.size} color={pal.card_ink} x={40} y={0} w={560} frame={frame} fps={fps}
          delay={0.1} align="center" />
      </Card>,
    );
  } else if (L === "keyword") {
    const open = enter(frame, fps, 0, 180);
    const land = spring({ frame: frame - 2, fps, from: 1.5, to: 1, config: { damping: 9, stiffness: 180 } });
    content.push(
      <Label key="l" text="Anahtar kelime" x={62} y={294} color={pal.soft} frame={frame} fps={fps} />,
      <Abs key="k" x={0} y={430} w={720} h={180} style={{ display: "grid", placeItems: "center" }}>
        <div style={{ background: hex(pal.accent), borderRadius: 999, padding: `${scene.keywordSize * 0.15}px ${scene.keywordSize * 0.45}px`,
                      transform: `scaleY(${open})`, boxShadow: `0 0 40px ${hex(pal.accent)}66` }}>
          <div style={{ fontFamily: HEAD, fontWeight: 700, fontSize: scene.keywordSize, color: hex(pal.on_accent),
                        transform: `scale(${land})`, letterSpacing: -1 }}>{scene.keyword}</div>
        </div>
      </Abs>,
      <Lines key="ctx" text={scene.text} size={scene.size} color={pal.soft} x={60} y={680} w={600} frame={frame} fps={fps}
        delay={0.35} align="center" weight={400} />,
    );
  } else if (L === "quote") {
    const pop = spring({ frame, fps, from: 1.4, to: 1, config: { damping: 12 } });
    const bar = enter(frame, fps, 0.08, 440);
    content.push(
      <Abs key="q" x={58} y={262} style={{ fontFamily: HEAD, fontWeight: 700, fontSize: 150, lineHeight: 1,
                                            color: hex(pal.accent), transform: `scale(${pop})`, transformOrigin: "0 0" }}>“</Abs>,
      <Abs key="bar" x={62} y={380} w={6} h={330 * bar} style={{ background: hex(pal.ink), opacity: 0.8 }} />,
      <Lines key="t" text={scene.text} size={scene.size} color={pal.ink} x={92} y={386} w={580} frame={frame} fps={fps}
        delay={0.1} italic />,
    );
  } else if (L === "split") {
    const revealFrame = (scene.reveal - scene.start) * fps;
    scene.parts.forEach((part, number) => {
      const local = number ? frame - revealFrame : frame;
      if (local < 0) return;
      const top = number ? 500 : 290;
      const pop = spring({ frame: local, fps, config: { damping: 12 } });
      content.push(
        <Card key={`s${number}`} x={40} y={top} w={640} h={180} pal={pal} frame={local} fps={fps}>
          <Abs x={24} y={24} w={48} h={48}
            style={{ borderRadius: 24, background: hex(number ? pal.accent : pal.card_ink), transform: `scale(${pop})`,
                     display: "grid", placeItems: "center", color: hex(number ? pal.on_accent : pal.card),
                     fontFamily: HEAD, fontWeight: 700, fontSize: 24 }}>{number + 1}</Abs>
          <Lines text={part.text} size={part.size} color={pal.card_ink} x={90} y={28} w={520} frame={local} fps={fps} delay={0.06} />
        </Card>,
      );
    });
  } else if (L === "image" && plan.image) {
    // The chosen news image: a framed card with a slow Ken Burns push and a source credit.
    const p = enter(frame, fps, 0, 360);
    const push = 1.02 + 0.08 * clamp(frame / fps / Math.max(0.1, length));
    content.push(
      <Abs key="frame" x={40} y={290 + 40 * (1 - p)} w={640} h={430}
        style={{ opacity: p, borderRadius: 36, overflow: "hidden", border: `2px solid ${hex(pal.accent)}88`,
                 boxShadow: `0 20px 50px rgba(0,0,0,.35), 0 0 30px ${hex(pal.accent)}33` }}>
        <Img src={plan.image.src} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${push})` }} />
        {plan.image.credit ? (
          <Abs x={18} y={382} style={{ background: "rgba(0,0,0,.6)", color: "#FFFFFF", borderRadius: 14, padding: "5px 12px",
                                        fontFamily: BODY, fontSize: 15 }}>Görsel: {plan.image.credit}</Abs>
        ) : null}
      </Abs>,
      <Lines key="t" text={scene.text} size={scene.size} color={pal.ink} x={62} y={746} w={600} frame={frame} fps={fps}
        delay={0.25} weight={500} />,
    );
  } else if (L === "host") {
    const top = 268;
    const box = scene.text.split("\n").length * Math.round(scene.size * 1.18) + 96;
    const p = enter(frame, fps, 0, 320);
    content.push(
      <Abs key="bubble" x={40} y={top + 40 * (1 - p)} w={640} h={box}
        style={{ opacity: p, borderRadius: 36, background: hex(pal.card), boxShadow: "0 18px 40px rgba(0,0,0,.25)" }}>
        <Abs x={36} y={26} style={{ background: hex(pal.accent), color: hex(pal.on_accent), borderRadius: 16,
                                     padding: "5px 16px", fontFamily: BODY, fontWeight: 500, fontSize: 16 }}>{scene.label}</Abs>
        <Lines text={scene.text} size={scene.size} color={pal.card_ink} x={36} y={74} w={570} frame={frame} fps={fps} delay={0.1} />
        <svg width={80} height={60} style={{ position: "absolute", left: 260, top: box - 2 }}>
          <path d="M 0 0 L 64 0 L 18 48 Z" fill={hex(pal.card)} />
        </svg>
      </Abs>,
    );
  } else {
    const bar = enter(frame, fps, 0.36, 440);
    content.push(
      <Label key="l" text="Yakın plan" x={62} y={268} color={pal.soft} frame={frame} fps={fps} />,
      <Abs key="hl" x={50} y={316 + scene.size * 0.62} w={Math.min(620, scene.text.split("\n")[0].length * scene.size * 0.52) * bar}
        h={scene.size * 0.42} style={{ background: hex(pal.accent), opacity: 0.55, borderRadius: 6 }} />,
      <Lines key="t" text={scene.text} size={scene.size} color={pal.ink} x={62} y={316} w={620} frame={frame} fps={fps} />,
    );
  }

  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: hex(pal.panel) }} />
      <Grid ink={pal.ink} />
      <Timeline pal={pal} frame={frame} fps={fps}
        brandPill={scene.brandHere && L !== "hook" ? <BrandMark mark={plan.brandMark} hero={false} pal={pal} frame={frame} fps={fps} /> : null} />
      {content}
    </AbsoluteFill>
  );
};

// Front layer of a scene: name tags and the hero brand mark, above the host.
const SceneFront = ({ scene, plan }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pal = scene.palette;
  const items = [];
  if (scene.brandHere && scene.layout === "hook")
    items.push(<BrandMark key="b" mark={plan.brandMark} hero pal={pal} frame={frame} fps={fps} />);
  if (plan.host && scene.host === "big") {
    const p = enter(frame, fps, 0, 320);
    items.push(
      <Abs key="tag" x={52 - 272 * (1 - p)} y={860}
        style={{ background: hex(pal.accent), color: hex(pal.on_accent), borderRadius: 23, padding: "9px 22px 9px 16px",
                 fontFamily: HEAD, fontWeight: 700, fontSize: 22, display: "flex", alignItems: "center", gap: 10,
                 boxShadow: `0 0 22px ${hex(pal.accent)}55` }}>
        <span style={{ width: 12, height: 12, borderRadius: 6, background: hex(pal.on_accent) }} />{plan.host.name}
      </Abs>,
    );
  } else if (plan.host && scene.host === "pip" && !scene.roaming) {
    const [cx, cy, r] = plan.host.pip;
    const p = enter(frame, fps, 0.1, 220);
    items.push(
      <Abs key="ring" x={cx - r + 4} y={cy - r + 4} w={2 * r - 8} h={2 * r - 8}
        style={{ borderRadius: r, border: `6px solid ${hex(pal.accent)}`, opacity: p, boxShadow: `0 0 16px ${hex(pal.accent)}88` }} />,
      <Abs key="name" x={cx - 60} y={cy + r - 20} w={120} style={{ display: "grid", placeItems: "center", opacity: p }}>
        <div style={{ background: hex(pal.accent), color: hex(pal.on_accent), borderRadius: 15, padding: "4px 14px",
                      fontFamily: HEAD, fontWeight: 700, fontSize: 16 }}>{plan.host.name}</div>
      </Abs>,
    );
  }
  return <AbsoluteFill>{items}</AbsoluteFill>;
};

// --- host ---------------------------------------------------------------------------

const Host = ({ host }) => {
  const frame = useCurrentFrame();
  const track = host.track;
  const shot = track.frames[Math.min(track.frames.length - 1, frame)];
  if (!shot) return null;
  const [cx, cy, r] = track.clip;
  return (
    <svg width={720} height={1280} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
      <defs>
        <clipPath id="pip-clip"><circle cx={cx} cy={cy} r={r} /></clipPath>
      </defs>
      <g clipPath={shot.clip ? "url(#pip-clip)" : undefined}>
        {shot.groups.map((group, g) => (
          <g key={g} transform={group.transform}>
            {group.parts.map(([id, fill, opacity, glow, stroke], i) => (
              <path key={i} d={track.paths[id]} fill={hex(fill)} fillOpacity={opacity} fillRule="nonzero"
                stroke={stroke ? hex(stroke) : undefined} strokeWidth={stroke ? 9 : undefined}
                strokeLinejoin="round" paintOrder="stroke"
                style={glow ? { filter: `drop-shadow(0 0 6px ${hex(fill)})` } : undefined} />
            ))}
          </g>
        ))}
      </g>
    </svg>
  );
};

// --- camera -------------------------------------------------------------------------

const cameraAt = (camera, t) => {
  let z = 1;
  let fx = 360;
  let fy = 640;
  for (const moment of camera) {
    const rise = clamp((t - (moment.start - 0.28)) / 0.28);
    const fall = clamp((moment.end + 0.5 + 0.7 - t) / 0.7);
    const b = smooth(Math.min(rise, fall));
    z += moment.strength * b;
    fx += (moment.focus[0] - 360) * b;
    fy += (moment.focus[1] - 640) * b;
  }
  // Keep the visible region inside the world so no edge is ever exposed.
  fx = Math.min(720 - 360 / z, Math.max(360 / z, fx));
  fy = Math.min(1280 - 640 / z, Math.max(640 / z, fy));
  return { z, fx, fy };
};

// --- HUD ----------------------------------------------------------------------------

const Captions = ({ captions, pop }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const burst = captions.find((item) => item.start <= t && t < item.end);
  if (!burst) return null;
  const entrance = spring({ frame: frame - burst.start * fps, fps, from: 0.7, to: 1, config: { damping: 12, stiffness: 220 } });
  return (
    <Abs x={40} y={0} w={640} style={{ top: undefined, bottom: 1280 - CAPTION_Y, textAlign: "center",
                                       transform: `rotate(${burst.tilt}deg) scale(${entrance})` }}>
      <div style={{ fontFamily: HEAD, fontWeight: 700, fontSize: 62, lineHeight: 1.08, color: "#FFFFFF",
                    WebkitTextStroke: "12px #2B2C2E", paintOrder: "stroke fill",
                    textShadow: "0 6px 0 rgba(0,0,0,.35)" }}>
        {burst.words.map((word, i) => {
          const shown = t >= word.start;
          const active = t >= word.start && t < word.end;
          const local = frame - word.start * fps;
          const scale = active
            ? spring({ frame: local, fps, from: word.stressed ? 1.75 : 1.22, to: word.stressed ? 1.45 : 1,
                       config: { damping: 10, stiffness: 240 } })
            : 1;
          return (
            <React.Fragment key={i}>
              <span style={{ display: "inline-block", opacity: shown ? 1 : 0, color: active ? hex(pop) : "#FFFFFF",
                             transform: `scale(${scale})`, margin: word.stressed && shown ? "0 26px" : "0 6px" }}>{word.text}</span>
              {" "}
            </React.Fragment>
          );
        })}
      </div>
    </Abs>
  );
};

const Hud = ({ plan, scene, index }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pal = scene.palette;
  const { pack } = plan;
  const count = plan.scenes.length;
  const dots = plan.scenes.map((_, i) => Math.round(150 + (480 * (i + 0.5)) / count));
  const dot = spring({ frame: frame - scene.start * fps, fps, config: { damping: 12 } });
  return (
    <>
      <svg width={720} height={200} style={{ position: "absolute", left: 0, top: 0 }}>
        <path d="M 18 62 Q 18 18 62 18 L 346 18 Q 390 18 390 62 L 390 150 L 18 150 Z" fill={hex(pal.panel)} />
        <path d="M 390 104 L 390 150 L 436 150 C 411 150 390 129 390 104 Z" fill={hex(pal.panel)} />
      </svg>
      <Abs x={44} y={54} w={60} h={60} style={{ borderRadius: 30, background: "#FFFFFF", display: "grid", placeItems: "center",
                                               color: hex(pack.frame), fontFamily: HEAD, fontWeight: 700, fontSize: 30 }}>
        {plan.brand.slice(0, 1).toUpperCase()}
      </Abs>
      <Abs x={120} y={44} style={{ fontFamily: HEAD, fontWeight: 700, fontSize: 44, color: hex(pal.ink), letterSpacing: -1 }}>{plan.brand}</Abs>
      <Abs x={122} y={100} style={{ fontFamily: BODY, fontSize: 17, color: hex(pal.soft) }}>Teknoloji gündemi</Abs>
      <Abs x={408} y={49} style={{ display: "flex", gap: 8 }}>
        <div style={{ background: "#F6F5F1", color: "#2B2C2E", borderRadius: 26, padding: "14px 22px", fontFamily: BODY,
                      fontWeight: 500, fontSize: 18 }}>{scene.label}</div>
        <div style={{ background: "#57585B", color: "#FFFFFF", borderRadius: 26, padding: "14px 18px", fontFamily: BODY,
                      fontSize: 17 }}>{String(index + 1).padStart(2, "0")} / {String(count).padStart(2, "0")}</div>
      </Abs>
      <Abs x={40} y={1158} w={640} h={66} style={{ borderRadius: 33, background: pack.cyber ? "#141B2B" : "#FFFFFF" }}>
        <Abs x={14} y={7} w={52} h={52} style={{ borderRadius: 26, background: hex(pack.frame), display: "grid", placeItems: "center" }}>
          <div style={{ width: 18, height: 16, borderRadius: 4, background: hex(pack.pop) }} />
        </Abs>
      </Abs>
      {dots.map((x, i) => (
        <React.Fragment key={i}>
          {i === index ? (
            <Abs x={x - 32} y={1169} w={64} h={44} style={{ borderRadius: 22, background: pack.cyber ? "#2A3450" : hex(pack.frame) }}>
              <Abs x={25} y={15} w={14} h={14} style={{ borderRadius: 7, background: hex(pack.pop), transform: `scale(${dot})`,
                                                        boxShadow: `0 0 10px ${hex(pack.pop)}` }} />
            </Abs>
          ) : (
            <Abs x={x - 6} y={1185} w={12} h={12}
              style={{ borderRadius: 6, background: i < index ? hex(pack.pop) : pack.cyber ? "#39445C" : "#D3D1CA",
                       opacity: i < index ? 0.75 : 1 }} />
          )}
        </React.Fragment>
      ))}
      {pack.cyber ? (
        <>
          {[[30, 162, 1, 1], [690, 162, -1, 1], [30, 1250, 1, -1], [690, 1250, -1, -1]].map(([x, y, sx, sy], i) => (
            <svg key={i} width={720} height={1280} style={{ position: "absolute", left: 0, top: 0 }}>
              <path d={`M ${x} ${y} L ${x + 46 * sx} ${y} L ${x + 46 * sx} ${y + 4 * sy} L ${x + 4 * sx} ${y + 4 * sy} L ${x + 4 * sx} ${y + 46 * sy} L ${x} ${y + 46 * sy} Z`}
                fill={hex(pack.pop)} opacity={0.85} style={{ filter: `drop-shadow(0 0 4px ${hex(pack.pop)})` }} />
            </svg>
          ))}
          <AbsoluteFill style={{ backgroundImage: "repeating-linear-gradient(0deg, rgba(0,0,0,.09) 0px, rgba(0,0,0,.09) 1px, transparent 1px, transparent 5px)",
                                 top: 150, height: 1112, pointerEvents: "none" }} />
        </>
      ) : null}
    </>
  );
};

// --- composition --------------------------------------------------------------------

export const Video = ({ plan }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const scenes = plan.scenes;
  const index = Math.max(0, scenes.findIndex((scene) => scene.start <= t && t < scene.end));
  const current = scenes[index] || scenes[scenes.length - 1];
  if (!current) return <AbsoluteFill style={{ background: hex(plan.pack.frame) }} />;
  const { z, fx, fy } = cameraAt(plan.camera, t);
  const span = (scene) => ({ from: Math.round(scene.start * fps), durationInFrames: Math.max(1, Math.round((scene.end - scene.start) * fps)) });
  return (
    <AbsoluteFill style={{ background: hex(plan.pack.frame) }}>
      <Abs x={18} y={150} w={684} h={1112} style={{ borderRadius: 44, overflow: "hidden" }}>
        <Abs x={-18} y={-150} w={720} h={1280}
          style={{ transformOrigin: "0 0", transform: `translate(${360 - fx * z}px, ${640 - fy * z}px) scale(${z})` }}>
          {scenes.map((scene) => (
            <Sequence key={`b${scene.index}`} {...span(scene)} layout="none">
              <SceneBack scene={scene} plan={plan} />
            </Sequence>
          ))}
          {plan.host ? <Host host={plan.host} /> : null}
          {scenes.map((scene) => (
            <Sequence key={`f${scene.index}`} {...span(scene)} layout="none">
              <SceneFront scene={scene} plan={plan} />
            </Sequence>
          ))}
          {scenes.slice(1).map((scene) => {
            const local = t - (scene.start - 0.18);
            if (local < 0 || local > 0.42) return null;
            const fade = Math.min(clamp(local / 0.14), clamp((0.32 - local) / 0.14));
            return (
              <React.Fragment key={`w${scene.index}`}>
                <AbsoluteFill style={{ background: hex(scene.palette.panel), opacity: fade }} />
                <Abs x={-100} y={262 + 838 * clamp(local / 0.42)} w={920} h={12}
                  style={{ background: hex(scene.palette.accent), boxShadow: `0 0 24px ${hex(scene.palette.accent)}` }} />
              </React.Fragment>
            );
          })}
        </Abs>
      </Abs>
      <Hud plan={plan} scene={current} index={index} />
      <Captions captions={plan.captions} pop={plan.pack.pop} />
    </AbsoluteFill>
  );
};
