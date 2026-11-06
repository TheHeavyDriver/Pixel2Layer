'use client';

import type { SceneGraphElement } from '@pixel2layer/schema';
import { Section, Field, num } from './shared';
import { FillControls } from './fill-controls';

export function VectorProperties({
  element,
  onUpdateElement,
}: {
  element: Extract<SceneGraphElement, { type: 'vector' }>;
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
}) {
  return (
    <>
      <Section title="Fill">
        <FillControls element={element} onUpdateElement={onUpdateElement} styleKey="fill" />
      </Section>
      <Section title="Geometry">
        <Field label="Width">
          <input
            type="number"
            min={1}
            value={Math.round(element.width)}
            onChange={(e) => {
              const v = num(e.target.value);
              if (Number.isFinite(v) && v > 0) onUpdateElement(element.id, { width: v });
            }}
            className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
        <Field label="Height">
          <input
            type="number"
            min={1}
            value={Math.round(element.height)}
            onChange={(e) => {
              const v = num(e.target.value);
              if (Number.isFinite(v) && v > 0) onUpdateElement(element.id, { height: v });
            }}
            className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
      </Section>
      <Section title="Path">
        <textarea
          value={element.path}
          rows={4}
          spellCheck={false}
          onChange={(e) => onUpdateElement(element.id, { path: e.target.value })}
          className="w-full resize-y rounded-md border border-bordered bg-raised p-2 font-mono text-[11px] leading-snug text-primary focus:border-bordered-strong focus:outline-none"
          aria-label="SVG path"
        />
        <p className="mt-1 text-[11px] text-muted">
          Editable SVG path data (M/L/C/Q/Z). Coordinates are local to the
          element; origin sits at the element center.
        </p>
      </Section>
    </>
  );
}
