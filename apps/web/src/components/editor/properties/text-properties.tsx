'use client';

import type { SceneGraphElement } from '@pixel2layer/schema';
import {
  FONT_CATEGORY_LABELS,
  designFontListWith,
  type DesignFontCategory,
} from '@/lib/design-fonts';
import { Section, Field, num } from './shared';
import { FillControls } from './fill-controls';

function fontOptions(family: string | undefined) {
  const entries = designFontListWith(family);
  const groups = new Map<DesignFontCategory, { family: string }[]>();
  for (const entry of entries) {
    const list = groups.get(entry.category) ?? [];
    list.push(entry);
    groups.set(entry.category, list);
  }
  return (
    <>
      {[...groups.entries()].map(([category, list]) => (
        <optgroup key={category} label={FONT_CATEGORY_LABELS[category]}>
          {list.map((entry) => (
            <option key={entry.family} value={entry.family}>
              {entry.family}
            </option>
          ))}
        </optgroup>
      ))}
    </>
  );
}

export function TextProperties({
  element,
  onUpdateElement,
}: {
  element: Extract<SceneGraphElement, { type: 'text' }>;
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
}) {
  return (
    <>
      <Section title="Content">
        <textarea
          value={element.content}
          rows={2}
          onChange={(e) => onUpdateElement(element.id, { content: e.target.value })}
          className="w-full resize-y rounded-md border border-bordered bg-raised p-2 font-mono text-[13px] leading-snug text-primary focus:border-bordered-strong focus:outline-none"
          aria-label="Text content"
        />
      </Section>
      <Section title="Font">
        <Field label="Family">
          <select
            value={element.fontFamily}
            onChange={(e) => onUpdateElement(element.id, { fontFamily: e.target.value })}
            className="h-7 w-full rounded-md border border-bordered bg-raised px-2 text-[12px] text-primary focus:border-bordered-strong focus:outline-none"
          >
            {fontOptions(element.fontFamily)}
          </select>
        </Field>
        <Field label="Size">
          <input
            type="number"
            value={element.fontSize}
            onChange={(e) => {
              const v = num(e.target.value);
              if (Number.isFinite(v) && v > 0) onUpdateElement(element.id, { fontSize: v });
            }}
            className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
        <Field label="Weight">
          <input
            type="range"
            min={100}
            max={900}
            step={100}
            value={element.fontWeight}
            onChange={(e) => onUpdateElement(element.id, { fontWeight: Number(e.target.value) })}
            className="h-7 w-full accent-[var(--accent)]"
          />
        </Field>
        <Field label="Align">
          <div className="flex gap-1">
            {(['left', 'center', 'right'] as const).map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => onUpdateElement(element.id, { textAlign: a })}
                className={`h-7 flex-1 rounded-md border text-[11px] capitalize transition-colors ${
                  (element.textAlign ?? 'left') === a
                    ? 'border-accent bg-accent/10 text-primary'
                    : 'border-bordered bg-raised text-secondary hover:bg-raised'
                }`}
              >
                {a}
              </button>
            ))}
          </div>
        </Field>
      </Section>
      <Section title="Text Color">
        <FillControls element={element} onUpdateElement={onUpdateElement} styleKey="fill" />
      </Section>
    </>
  );
}
