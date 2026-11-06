'use client';

import { useState } from 'react';
import type { SceneGraphElement } from '@pixel2layer/schema';
import { Field, normalizeHex } from './shared';

export function FillControls({
  element,
  onUpdateElement,
  styleKey,
}: {
  element: SceneGraphElement;
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
  styleKey: 'fill' | 'stroke';
}) {
  const value = element[styleKey] ?? '#000000';
  const [hex, setHex] = useState(value);
  return (
    <>
      <Field label="Color">
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={normalizeHex(value)}
            onChange={(e) => {
              const next = e.target.value;
              setHex(next);
              onUpdateElement(element.id, { [styleKey]: next } as Partial<SceneGraphElement>);
            }}
            className="h-7 w-9 cursor-pointer rounded border border-bordered bg-raised p-0.5"
            aria-label={`${styleKey} color`}
          />
          <input
            value={hex}
            onChange={(e) => setHex(e.target.value)}
            onBlur={() => {
              const next = normalizeHex(hex);
              setHex(next);
              onUpdateElement(element.id, { [styleKey]: next } as Partial<SceneGraphElement>);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const next = normalizeHex(hex);
                setHex(next);
                onUpdateElement(element.id, { [styleKey]: next } as Partial<SceneGraphElement>);
                e.currentTarget.blur();
              }
            }}
            className="h-7 flex-1 rounded-md border border-bordered bg-raised px-2 font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
            aria-label={`${styleKey} hex`}
          />
        </div>
      </Field>
      <Field label="Opacity">
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(element.opacity * 100)}
          onChange={(e) => onUpdateElement(element.id, { opacity: Number(e.target.value) / 100 })}
          className="h-7 w-full accent-[var(--accent)]"
        />
      </Field>
    </>
  );
}
