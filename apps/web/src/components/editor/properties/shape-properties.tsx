'use client';

import type { SceneGraphElement } from '@pixel2layer/schema';
import { Section, Field, num } from './shared';
import { FillControls } from './fill-controls';

export function RectangleProperties({
  element,
  onUpdateElement,
}: {
  element: Extract<SceneGraphElement, { type: 'rectangle' }>;
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
            value={element.width}
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
            value={element.height}
            onChange={(e) => {
              const v = num(e.target.value);
              if (Number.isFinite(v) && v > 0) onUpdateElement(element.id, { height: v });
            }}
            className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
        <Field label="Radius">
          <input
            type="number"
            min={0}
            value={element.rx ?? 0}
            onChange={(e) => {
              const v = Math.max(0, num(e.target.value) || 0);
              onUpdateElement(element.id, { rx: v, ry: v });
            }}
            className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
      </Section>
    </>
  );
}

export function CircleProperties({
  element,
  onUpdateElement,
}: {
  element: Extract<SceneGraphElement, { type: 'circle' }>;
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
}) {
  return (
    <>
      <Section title="Fill">
        <FillControls element={element} onUpdateElement={onUpdateElement} styleKey="fill" />
      </Section>
      <Section title="Geometry">
        <Field label="Radius">
          <input
            type="number"
            min={1}
            value={element.radius}
            onChange={(e) => {
              const v = num(e.target.value);
              if (Number.isFinite(v) && v > 0) onUpdateElement(element.id, { radius: v });
            }}
            className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
      </Section>
    </>
  );
}

export function EllipseProperties({
  element,
  onUpdateElement,
}: {
  element: Extract<SceneGraphElement, { type: 'ellipse' }>;
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
}) {
  return (
    <>
      <Section title="Fill">
        <FillControls element={element} onUpdateElement={onUpdateElement} styleKey="fill" />
      </Section>
      <Section title="Geometry">
        <Field label="RX">
          <input
            type="number"
            min={1}
            value={element.rx}
            onChange={(e) => {
              const v = num(e.target.value);
              if (Number.isFinite(v) && v > 0) onUpdateElement(element.id, { rx: v });
            }}
            className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
        <Field label="RY">
          <input
            type="number"
            min={1}
            value={element.ry}
            onChange={(e) => {
              const v = num(e.target.value);
              if (Number.isFinite(v) && v > 0) onUpdateElement(element.id, { ry: v });
            }}
            className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
          />
        </Field>
      </Section>
    </>
  );
}

export function LineProperties({
  element,
  onUpdateElement,
}: {
  element: Extract<SceneGraphElement, { type: 'line' }>;
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
}) {
  return (
    <Section title="Stroke">
      <FillControls element={element} onUpdateElement={onUpdateElement} styleKey="stroke" />
      <Field label="Width">
        <input
          type="number"
          min={1}
          value={element.strokeWidth ?? 1}
          onChange={(e) => {
            const v = num(e.target.value);
            if (Number.isFinite(v) && v > 0) onUpdateElement(element.id, { strokeWidth: v });
          }}
          className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
        />
      </Field>
    </Section>
  );
}
