'use client';

import type { SceneGraph, SceneGraphElement } from '@pixel2layer/schema';
import { Section, Field, num } from './properties/shared';
import { FillControls } from './properties/fill-controls';
import { TextProperties } from './properties/text-properties';
import {
  RectangleProperties,
  CircleProperties,
  EllipseProperties,
  LineProperties,
} from './properties/shape-properties';
import { VectorProperties } from './properties/vector-properties';
import { ImageProperties } from './properties/image-properties';
import { CanvasProperties } from './properties/canvas-properties';

interface PropertiesPanelProps {
  scene: SceneGraph;
  selectedIds: string[];
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
  onUpdateCanvas: (patch: Partial<SceneGraph['canvas']>) => void;
}

function transformOn(
  el: SceneGraphElement,
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void,
) {
  return (
    <Section title="Transform">
      <Field label="X">
        <input
          type="number"
          value={Math.round(el.transform.x)}
          onChange={(e) => {
            const v = num(e.target.value);
            if (Number.isFinite(v)) onUpdateElement(el.id, { transform: { ...el.transform, x: v } });
          }}
          className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
        />
      </Field>
      <Field label="Y">
        <input
          type="number"
          value={Math.round(el.transform.y)}
          onChange={(e) => {
            const v = num(e.target.value);
            if (Number.isFinite(v)) onUpdateElement(el.id, { transform: { ...el.transform, y: v } });
          }}
          className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
        />
      </Field>
      <Field label="Rotation">
        <input
          type="number"
          value={Math.round(el.transform.rotation)}
          onChange={(e) => {
            const v = num(e.target.value);
            if (Number.isFinite(v)) onUpdateElement(el.id, { transform: { ...el.transform, rotation: v } });
          }}
          className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
        />
      </Field>
      <Field label="Opacity">
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(el.opacity * 100)}
          onChange={(e) => onUpdateElement(el.id, { opacity: Number(e.target.value) / 100 })}
          className="h-7 w-full accent-[var(--accent)]"
        />
      </Field>
    </Section>
  );
}

function renderSingle(
  el: SceneGraphElement,
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void,
): React.ReactNode {
  switch (el.type) {
    case 'text':
      return <TextProperties element={el} onUpdateElement={onUpdateElement} />;
    case 'rectangle':
      return <RectangleProperties element={el} onUpdateElement={onUpdateElement} />;
    case 'circle':
      return <CircleProperties element={el} onUpdateElement={onUpdateElement} />;
    case 'ellipse':
      return <EllipseProperties element={el} onUpdateElement={onUpdateElement} />;
    case 'line':
      return <LineProperties element={el} onUpdateElement={onUpdateElement} />;
    case 'vector':
      return <VectorProperties element={el} onUpdateElement={onUpdateElement} />;
    case 'image':
      return <ImageProperties element={el} onUpdateElement={onUpdateElement} />;
    default:
      return (
        <Section title="Fill">
          <FillControls element={el} onUpdateElement={onUpdateElement} styleKey="fill" />
        </Section>
      );
  }
}

export function PropertiesPanel({
  scene,
  selectedIds,
  onUpdateElement,
  onUpdateCanvas,
}: PropertiesPanelProps) {
  const selected = scene.layers.filter((l) => selectedIds.includes(l.id));
  const primary = selected[0];
  const multi = selected.length > 1;

  if (selected.length === 0) {
    return (
      <aside
        className="flex h-full w-[280px] flex-col overflow-y-auto border-l border-bordered bg-surface"
        data-testid="properties-panel"
      >
        <CanvasProperties
          scene={scene}
          onUpdateCanvas={onUpdateCanvas}
        />
      </aside>
    );
  }

  return (
    <aside
      className="flex h-full w-[280px] flex-col overflow-y-auto border-l border-bordered bg-surface"
      data-testid="properties-panel"
    >
      <div className="flex h-[44px] items-center justify-between border-b border-bordered px-3">
        <h2 className="text-[13px] font-semibold tracking-[-0.01em]">
          {multi ? `${selected.length} elements` : primary?.name ?? 'Properties'}
        </h2>
      </div>
      {!multi && primary && (
        <div className="flex items-center gap-2 border-b border-bordered px-3 py-2">
          <span className="rounded-md bg-raised px-2 py-0.5 font-mono text-[11px] text-secondary">
            {primary.type}
          </span>
          <span
            className={`font-mono text-[11px] ${
              primary.confidence >= 0.8
                ? 'text-success'
                : primary.confidence >= 0.5
                  ? 'text-warning'
                  : 'text-danger'
            }`}
            title={primary.confidenceNote ?? undefined}
          >
            {Math.round(primary.confidence * 100)}% confidence
          </span>
          {primary.confidenceNote && (
            <span className="ml-auto max-w-[120px] truncate text-[11px] text-muted" title={primary.confidenceNote}>
              {primary.confidenceNote}
            </span>
          )}
        </div>
      )}
      {!multi && primary ? renderSingle(primary, onUpdateElement) : (
        <p className="px-3 py-4 text-[12px] text-secondary">
          {selected.length} elements selected. Use the toolbar for align and
          distribute.
        </p>
      )}
      {!multi && primary && transformOn(primary, onUpdateElement)}
    </aside>
  );
}
