import React from "react";
import type { RiskTrendPoint } from "../api/types";

interface Props {
  points: RiskTrendPoint[];
  width?: number;
  height?: number;
  color?: string;
}

export default function RiskSparkline({ points, width = 80, height = 28, color = "#6366f1" }: Props) {
  if (points.length < 2) return null;

  const scores = points.map((p) => p.risk_score ?? 0);
  const minV = Math.min(...scores);
  const maxV = Math.max(...scores);
  const range = maxV - minV || 1;

  const pad = 2;
  const xs = scores.map((_, i) => pad + (i / (scores.length - 1)) * (width - pad * 2));
  const ys = scores.map((s) => pad + ((maxV - s) / range) * (height - pad * 2));

  const polyline = xs.map((x, i) => `${x},${ys[i]}`).join(" ");

  // Trend arrow color
  const last = scores[scores.length - 1];
  const first = scores[0];
  const trendColor = last > first + 5 ? "#f87171" : last < first - 5 ? "#4ade80" : "#fbbf24";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ overflow: "visible" }}
      aria-hidden
    >
      {/* Area fill */}
      <defs>
        <linearGradient id={`sg-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={trendColor} stopOpacity="0.3" />
          <stop offset="100%" stopColor={trendColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <polygon
        points={`${xs[0]},${height} ${polyline} ${xs[xs.length - 1]},${height}`}
        fill={`url(#sg-${color.replace("#", "")})`}
      />
      {/* Line */}
      <polyline
        points={polyline}
        fill="none"
        stroke={trendColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Last point dot */}
      <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="2.5" fill={trendColor} />
    </svg>
  );
}
