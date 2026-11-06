'use client';

import { useState } from 'react';
import type { SceneGraph } from '@pixel2layer/schema';
import { Section, Field, normalizeHex } from './shared';

export function CanvasProperties({
  scene,
  onUpdateCanvas,
}: {
  scene: SceneGraph;
  onUpdateCanvas: (patch: Partial<SceneGraph['canvas']>) => void;
}) {
  const [width, setWidth] = useState(String(scene.canvas.width));
  const [height, setHeight] = useState(String(scene.canvas.height));
  return (
    <>
      <div className="flex h-[44px] items-center border-b border-bordered px-3">
        <h2 className="text-[13px] font-semibold tracking-[-0.01em]">Canvas</h2>
      </div>
      <Section title="Size">
        <Field label="Width">
          <input
            type="number"
            value={width}
            onChange={(e) => setWidth(e.target.value)}
            onBlur={() => {
              const v = Number(width);
              if (Number.isFinite(v) && v > 0) onUpdateCanvas({ width: v });
            }}
            className="h-7 w-full rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
        <Field label="Height">
          <input
            type="number"
            value={height}
            onChange={(e) => setHeight(e.target.value)}
            onBlur={() => {
              const v = Number(height);
              if (Number.isFinite(v) && v > 0) onUpdateCanvas({ height: v });
            }}
            className="h-7 w-full rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
      </Section>
      <Section title="Background">
        <Field label="Color">
          <input
            type="color"
            value={scene.canvas.background ? normalizeHex(scene.canvas.background) : '#ffffff'}
            onChange={(e) => onUpdateCanvas({ background: e.target.value })}
            className="h-7 w-full cursor-pointer rounded border border-bordered bg-raised p-0.5"
            aria-label="Canvas background color"
          />
        </Field>
      </Section>
      <Section title="Reconstruction">
        <p className="font-mono text-[12px]">
          <span
            className={
              scene.overallConfidence >= 0.8
                ? 'text-success'
                : scene.overallConfidence >= 0.5
                  ? 'text-warning'
                  : 'text-danger'
            }
          >
            {Math.round(scene.overallConfidence * 100)}%
          </span>{' '}
          <span className="text-muted">overall</span>
        </p>
        {scene.complexity?.kind && (
          <p className="mt-1 flex items-center gap-1 font-mono text-[12px]">
            <span className="capitalize text-secondary">{scene.complexity.kind}</span>
            <span className="text-muted">
              source ({scene.complexity.score != null
                ? `${Math.round(scene.complexity.score * 100)}% complexity`
                : 'detected'})
            </span>
          </p>
        )}
        {Object.entries(scene.confidence).map(([key, value]) => (
          <p key={key} className="mt-1 flex justify-between font-mono text-[12px]">
            <span className="capitalize text-secondary">{key}</span>
            <span
              className={
                value >= 0.8
                  ? 'text-success'
                  : value >= 0.5
                    ? 'text-warning'
                    : 'text-danger'
              }
            >
              {Math.round(value * 100)}%
            </span>
          </p>
        ))}
        <div className="mt-2 border-t border-bordered pt-2">
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.04em] text-muted">
            Element confidence
          </p>
          {scene.layers.length === 0 ? (
            <p className="font-mono text-[11px] text-muted">No layers</p>
          ) : (
            <ul className="max-h-40 space-y-0.5 overflow-y-auto">
              {[...scene.layers].reverse().map((el) => (
                <li
                  key={el.id}
                  className="flex items-center justify-between gap-2 font-mono text-[11px]"
                  title={el.confidenceNote ?? undefined}
                >
                  <span className="min-w-0 truncate text-secondary">{el.name}</span>
                  <span
                    className={
                      el.confidence >= 0.8
                        ? 'text-success'
                        : el.confidence >= 0.5
                          ? 'text-warning'
                          : 'text-danger'
                    }
                  >
                    {Math.round(el.confidence * 100)}%
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Section>
    </>
  );
}
