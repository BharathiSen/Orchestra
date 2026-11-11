"use client";

import { useEffect, useRef, useState } from "react";

import type { EvalRunSummary } from "@/lib/api";

// Data ink. #0d9488 passes the dataviz validator on the dark surface (#141a22):
// lightness band, chroma floor, and >= 3:1 contrast. The brighter UI accent
// does not sit in the dark-mode band, so marks use this step of the same hue.
const MARK = "#0d9488";
const SURFACE = "#141a22";
const GRID = "#232b36";

const Y_MIN = 1;
const Y_MAX = 5;

export type ScoreKey =
  | "avg_overall"
  | "avg_correctness"
  | "avg_completeness"
  | "avg_relevance"
  | "avg_clarity";

/**
 * One judged criterion across runs, oldest to newest. Runs are events, not a
 * time series, so they sit at even steps. The y-axis is fixed at 1-5 for every
 * chart, so small multiples can be compared by eye.
 */
export function ScoreTrend({
  runs,
  metric,
  title,
  height = 220,
  showRunLabels = true,
}: {
  runs: EvalRunSummary[];
  metric: ScoreKey;
  title: string;
  height?: number;
  showRunLabels?: boolean;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      setWidth(Math.max(240, Math.floor(entry.contentRect.width)));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const pad = { top: 16, right: 44, bottom: showRunLabels ? 44 : 14, left: 28 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const step = runs.length > 1 ? plotW / (runs.length - 1) : 0;
  const x = (i: number) => pad.left + (runs.length > 1 ? i * step : plotW / 2);
  const y = (v: number) => pad.top + ((Y_MAX - v) / (Y_MAX - Y_MIN)) * plotH;

  const points = runs.map((run, i) => ({ run, i, value: run[metric] }));
  // A missing score (nothing judged) breaks the line rather than faking a value.
  const segments: string[] = [];
  let current: string[] = [];
  for (const p of points) {
    if (p.value == null) {
      if (current.length > 1) segments.push(current.join(" "));
      current = [];
    } else {
      current.push(`${current.length ? "L" : "M"}${x(p.i)},${y(p.value)}`);
    }
  }
  if (current.length > 1) segments.push(current.join(" "));

  const last = [...points].reverse().find((p) => p.value != null);
  const hit = runs.length > 1 ? step : plotW;
  const activePoint = active != null ? points[active] : null;

  return (
    <figure className="rounded-2xl border border-line bg-surface p-4">
      <figcaption className="mb-2 flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold text-fg">{title}</span>
        <span className="text-[11px] text-fg-subtle">judge score, 1-5</span>
      </figcaption>
      <div ref={wrapRef} className="relative">
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={`${title}: ${points
            .map((p) => `${p.run.label} ${p.value ?? "not judged"}`)
            .join(", ")}`}
          onPointerLeave={() => setActive(null)}
        >
          {[1, 2, 3, 4, 5].map((tick) => (
            <g key={tick}>
              <line
                x1={pad.left}
                x2={width - pad.right}
                y1={y(tick)}
                y2={y(tick)}
                stroke={GRID}
                strokeWidth={1}
              />
              <text
                x={pad.left - 8}
                y={y(tick)}
                dy="0.32em"
                textAnchor="end"
                className="fill-fg-faint text-[10px]"
              >
                {tick}
              </text>
            </g>
          ))}

          {activePoint && (
            <line
              x1={x(activePoint.i)}
              x2={x(activePoint.i)}
              y1={pad.top}
              y2={pad.top + plotH}
              stroke="#5d6776"
              strokeWidth={1}
            />
          )}

          {segments.map((d) => (
            <path key={d} d={d} fill="none" stroke={MARK} strokeWidth={2} strokeLinejoin="round" />
          ))}

          {points.map((p) =>
            p.value == null ? null : (
              <circle
                key={p.run.id}
                cx={x(p.i)}
                cy={y(p.value)}
                r={active === p.i ? 5.5 : 4}
                fill={MARK}
                stroke={SURFACE}
                strokeWidth={2}
              />
            ),
          )}

          {/* One direct label, on the latest run: the number readers look for. */}
          {last && last.value != null && (
            <text
              x={x(last.i) + 9}
              y={y(last.value)}
              dy="0.32em"
              className="fill-fg text-[12px] font-semibold"
            >
              {last.value.toFixed(2)}
            </text>
          )}

          {showRunLabels &&
            points.map((p) => (
              <g key={`label-${p.run.id}`}>
                <text
                  x={x(p.i)}
                  y={pad.top + plotH + 18}
                  textAnchor="middle"
                  className="fill-fg-muted text-[11px]"
                >
                  {p.run.label.length > 18 ? `${p.run.label.slice(0, 17)}…` : p.run.label}
                </text>
                <text
                  x={x(p.i)}
                  y={pad.top + plotH + 32}
                  textAnchor="middle"
                  className="fill-fg-faint font-mono text-[10px]"
                >
                  {p.run.prompt_version}
                </text>
              </g>
            ))}

          {/* Hit areas: a full-height column per run, much wider than the dot,
              focusable so the same readout is reachable by keyboard. */}
          {points.map((p) => (
            <rect
              key={`hit-${p.run.id}`}
              x={x(p.i) - hit / 2}
              y={pad.top}
              width={Math.max(hit, 24)}
              height={plotH}
              fill="transparent"
              tabIndex={0}
              aria-label={`${p.run.label}, prompt ${p.run.prompt_version}: ${
                p.value == null ? "not judged" : p.value.toFixed(2)
              }`}
              onPointerEnter={() => setActive(p.i)}
              onFocus={() => setActive(p.i)}
              onBlur={() => setActive(null)}
              className="outline-none"
            />
          ))}
        </svg>

        {activePoint && (
          <div
            role="presentation"
            className="pointer-events-none absolute z-10 w-48 rounded-lg border border-line-strong bg-ground/95 px-3 py-2 text-xs shadow-lg"
            style={{
              left: Math.min(Math.max(x(activePoint.i) - 96, 0), width - 192),
              top: 0,
            }}
          >
            <p className="flex items-center gap-2">
              <span aria-hidden className="inline-block h-0.5 w-3" style={{ background: MARK }} />
              <span className="text-base font-semibold text-fg">
                {activePoint.value == null ? "—" : activePoint.value.toFixed(2)}
              </span>
            </p>
            <p className="mt-1 truncate text-fg-muted">{activePoint.run.label}</p>
            <p className="font-mono text-[11px] text-fg-subtle">
              prompts {activePoint.run.prompt_version} · {activePoint.run.model.replace("openai/", "")}
            </p>
          </div>
        )}
      </div>
    </figure>
  );
}
