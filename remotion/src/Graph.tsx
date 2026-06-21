import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";

const N = 9;
const COLLIDE = [2, 6];

export const Graph: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cx = 50;
  const cy = 50;
  const R = 38;

  const nodes = Array.from({ length: N }, (_, k) => {
    const a = (k / N) * Math.PI * 2 - Math.PI / 2;
    return { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R, k };
  });

  const centerScale = spring({ frame, fps, config: { damping: 14 }, durationInFrames: 20 });

  return (
    <svg viewBox="0 0 100 100" style={{ width: 470, height: 470, marginTop: 10 }}>
      {nodes.map((n, i) => {
        const appear = spring({ frame: frame - 14 - i * 4, fps, config: { damping: 16 }, durationInFrames: 18 });
        const ex = cx + (n.x - cx) * appear;
        const ey = cy + (n.y - cy) * appear;
        const isC = COLLIDE.includes(n.k);
        const pulse = isC ? 1 + 0.18 * Math.sin((frame - 60) / 6) : 1;
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={ex} y2={ey} stroke="rgba(255,122,26,0.5)" strokeWidth={0.5} />
            <circle cx={ex} cy={ey} r={(isC ? 2.6 : 1.7) * appear * pulse} fill={isC ? "#FF6A3D" : "#FF7A1A"} />
          </g>
        );
      })}
      <circle cx={cx} cy={cy} r={3.2 * centerScale} fill="#0b0806" stroke="#FFC24D" strokeWidth={1} />
    </svg>
  );
};
