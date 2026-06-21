import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame } from "remotion";
import { loadFont as loadPixel } from "@remotion/google-fonts/PixelifySans";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { SLIDES, Slide } from "./slides";
import { Graph } from "./Graph";

const pixel = loadPixel().fontFamily;
const inter = loadInter().fontFamily;
const mono = loadMono().fontFamily;

const ORANGE = "#FF7A1A";
const INK = "#F6EFE6";

const reveal = (frame: number, delay: number): React.CSSProperties => {
  const opacity = interpolate(frame, [delay, delay + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const y = interpolate(frame, [delay, delay + 12], [26, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return { opacity, transform: `translateY(${y}px)` };
};

const Backdrop: React.FC = () => (
  <>
    <AbsoluteFill style={{ background: "#000" }} />
    <AbsoluteFill
      style={{
        backgroundImage:
          "repeating-linear-gradient(90deg, rgba(255,255,255,0.05) 0, rgba(255,255,255,0.05) 1px, transparent 1px, transparent 96px)",
        WebkitMaskImage: "linear-gradient(to bottom, transparent, #000 14%, #000 86%, transparent)",
        maskImage: "linear-gradient(to bottom, transparent, #000 14%, #000 86%, transparent)",
      }}
    />
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(120% 80% at 50% 100%, rgba(240,72,10,0.22), rgba(255,122,26,0.05) 38%, transparent 70%)",
      }}
    />
  </>
);

const SlideView: React.FC<{ slide: Slide }> = ({ slide }) => {
  const frame = useCurrentFrame();
  const exit = interpolate(frame, [slide.dur - 14, slide.dur], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const big: React.CSSProperties = {
    fontFamily: pixel,
    textTransform: "uppercase",
    color: INK,
    fontWeight: 600,
    lineHeight: 1.04,
    letterSpacing: "0.01em",
    fontSize: 74,
  };

  return (
    <AbsoluteFill style={{ opacity: exit, justifyContent: "center", padding: "0 130px" }}>
      <div style={{ ...reveal(frame, 0), fontFamily: mono, letterSpacing: "0.22em", textTransform: "uppercase", color: "#C9A98F", fontSize: 21, marginBottom: 30, display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ width: 11, height: 11, background: ORANGE, boxShadow: `0 0 14px ${ORANGE}` }} />
        {slide.eyebrow}
      </div>

      {slide.title.map((line, i) => {
        const isLast = i === slide.title.length - 1;
        const accent = (slide.accentLast && isLast) || (slide.kind === "close" && i === 2);
        const dim = slide.kind === "close" && i === 1;
        return (
          <div key={i} style={{ ...big, ...reveal(frame, 8 + i * 5), color: accent ? ORANGE : dim ? "#C9A98F" : INK }}>
            {line}
          </div>
        );
      })}

      {slide.kind === "insight" && (
        <div style={reveal(frame, 24)}>
          <Graph />
        </div>
      )}

      {slide.lead && slide.kind !== "pills" && (
        <div style={{ ...reveal(frame, 22), fontFamily: inter, color: "#D8C8B8", fontSize: 30, lineHeight: 1.5, maxWidth: 880, marginTop: 30 }}>
          {slide.lead}
        </div>
      )}

      {slide.rows && (
        <div style={{ marginTop: 36, display: "flex", flexDirection: "column", gap: 18, maxWidth: 1180 }}>
          {slide.rows.map((r, i) => (
            <div key={i} style={{ ...reveal(frame, 24 + i * 8), display: "flex", gap: 20, alignItems: "flex-start" }}>
              <div style={{ flex: "none", width: 38, height: 38, borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: mono, fontWeight: 700, fontSize: 17, color: "#150a02", background: "linear-gradient(135deg,#FFC24D,#FF7A1A)" }}>{i + 1}</div>
              <div style={{ fontFamily: inter, fontSize: 27, lineHeight: 1.4, color: "#E7E9EC" }}>{r}</div>
            </div>
          ))}
        </div>
      )}

      {slide.verdict && (
        <div style={{ display: "flex", gap: 20, marginTop: 36 }}>
          {slide.verdict.map((v, i) => {
            const styles: Record<string, React.CSSProperties> = {
              ALLOW: { color: "#5F636D", border: "1px solid rgba(255,255,255,0.12)" },
              HOLD: { color: "#1c0d02", background: "linear-gradient(135deg,#FFC24D,#F5A623)" },
              BLOCK: { color: "#FF6A3D", border: "1px solid rgba(255,106,61,0.4)" },
            };
            return (
              <div key={i} style={{ ...reveal(frame, 24 + i * 8), fontFamily: pixel, fontSize: 46, padding: "18px 30px", borderRadius: 13, ...styles[v] }}>
                {v}
              </div>
            );
          })}
        </div>
      )}

      {slide.sub && (
        <div style={{ ...reveal(frame, 48), fontFamily: inter, color: "#B59B86", fontSize: 23, lineHeight: 1.6, maxWidth: 1000, marginTop: 26 }}>
          {slide.sub}
        </div>
      )}

      {slide.kind === "pills" && slide.lead && (
        <div style={{ ...reveal(frame, 22), fontFamily: inter, color: "#D8C8B8", fontSize: 28, lineHeight: 1.5, maxWidth: 900, marginTop: 28 }}>
          {slide.lead}
        </div>
      )}

      {slide.pills && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 13, marginTop: 30 }}>
          {slide.pills.map((p, i) => (
            <div key={i} style={{ ...reveal(frame, 40 + i * 6), fontFamily: mono, fontWeight: 600, fontSize: 22, color: i % 2 ? "#FFC24D" : "#34D399", background: i % 2 ? "rgba(255,122,26,0.09)" : "rgba(52,211,153,0.1)", border: `1px solid ${i % 2 ? "rgba(255,122,26,0.34)" : "rgba(52,211,153,0.34)"}`, borderRadius: 999, padding: "12px 18px" }}>
              {p}
            </div>
          ))}
        </div>
      )}
    </AbsoluteFill>
  );
};

const Hud: React.FC = () => {
  const frame = useCurrentFrame();
  const total = SLIDES.reduce((a, s) => a + s.dur, 0);
  const pct = (frame / total) * 100;
  let acc = 0;
  let idx = 0;
  for (let i = 0; i < SLIDES.length; i++) {
    if (frame >= acc) idx = i;
    acc += SLIDES[i].dur;
  }
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", top: 44, left: 56, fontFamily: pixel, letterSpacing: "0.12em", color: "#C9A98F", fontSize: 26 }}>KEYSTONE</div>
      <div style={{ position: "absolute", bottom: 40, left: 56, right: 56, height: 4, background: "rgba(255,255,255,0.08)", borderRadius: 2 }}>
        <div style={{ width: `${pct}%`, height: "100%", background: "linear-gradient(90deg,#FFC24D,#FF7A1A,#F0480A)", borderRadius: 2 }} />
      </div>
      <div style={{ position: "absolute", bottom: 56, right: 56, fontFamily: mono, color: "#8B9099", fontSize: 20 }}>
        {String(idx + 1).padStart(2, "0")} / {String(SLIDES.length).padStart(2, "0")}
      </div>
    </AbsoluteFill>
  );
};

export const KeystoneVideo: React.FC = () => {
  let from = 0;
  const seqs = SLIDES.map((slide, i) => {
    const node = (
      <Sequence key={i} from={from} durationInFrames={slide.dur}>
        <SlideView slide={slide} />
      </Sequence>
    );
    from += slide.dur;
    return node;
  });
  return (
    <AbsoluteFill>
      <Backdrop />
      {seqs}
      <Hud />
    </AbsoluteFill>
  );
};
