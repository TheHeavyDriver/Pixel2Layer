'use client';

import { useState, type ReactNode } from 'react';

import type { SceneGraph, SceneGraphElement } from '@pixel2layer/schema';

interface PropertiesPanelProps {
  scene: SceneGraph;
  selectedIds: string[];
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
  onUpdateCanvas: (patch: Partial<SceneGraph['canvas']>) => void;
}

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-b border-bordered px-3 py-3">
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.04em] text-muted">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="mb-2 flex items-center justify-between gap-2 last:mb-0">
      <span className="w-16 shrink-0 text-[12px] text-secondary">{label}</span>
      {children}
    </label>
  );
}

const num = (v: string) => (v === '' ? NaN : Number(v));

export function PropertiesPanel({
  scene,
  selectedIds,
  onUpdateElement,
  onUpdateCanvas,
}: PropertiesPanelProps) {
  const selected = scene.layers.filter((l) => selectedIds.includes(l.id));
  const primary = selected[0];
  const multi = selected.length > 1;

  // -- shared transform readout -----------------------------------------------
  function transformOn(el: SceneGraphElement) {
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

  function renderSingle(el: SceneGraphElement): React.ReactNode {
    if (el.type === 'text') {
      return (
        <>
          <Section title="Content">
            <textarea
              value={el.content}
              rows={2}
              onChange={(e) => onUpdateElement(el.id, { content: e.target.value })}
              className="w-full resize-y rounded-md border border-bordered bg-raised p-2 font-mono text-[13px] leading-snug text-primary focus:border-bordered-strong focus:outline-none"
              aria-label="Text content"
            />
          </Section>
          <Section title="Font">
            <Field label="Family">
              <select
                value={el.fontFamily}
                onChange={(e) => onUpdateElement(el.id, { fontFamily: e.target.value })}
                className="h-7 w-full rounded-md border border-bordered bg-raised px-2 text-[12px] text-primary focus:border-bordered-strong focus:outline-none"
              >
                <option value="sans-serif">Sans-serif</option>
                <option value="Arial">Arial</option>
                <option value="Georgia">Georgia</option>
                <option value="monospace">Monospace</option>
                <option value="Impact">Impact</option>
              </select>
            </Field>
            <Field label="Size">
              <input
                type="number"
                value={el.fontSize}
                onChange={(e) => {
                  const v = num(e.target.value);
                  if (Number.isFinite(v) && v > 0) onUpdateElement(el.id, { fontSize: v });
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
                value={el.fontWeight}
                onChange={(e) => onUpdateElement(el.id, { fontWeight: Number(e.target.value) })}
                className="h-7 w-full accent-[var(--accent)]"
              />
            </Field>
            <Field label="Align">
              <div className="flex gap-1">
                {(['left', 'center', 'right'] as const).map((a) => (
                  <button
                    key={a}
                    type="button"
                    onClick={() => onUpdateElement(el.id, { textAlign: a })}
                    className={`h-7 flex-1 rounded-md border text-[11px] capitalize transition-colors ${
                      (el.textAlign ?? 'left') === a
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
            <FillControls element={el} onUpdateElement={onUpdateElement} styleKey="fill" />
          </Section>
        </>
      );
    }

    if (el.type === 'rectangle') {
      return (
        <>
          <Section title="Fill">
            <FillControls element={el} onUpdateElement={onUpdateElement} styleKey="fill" />
          </Section>
          <Section title="Geometry">
            <Field label="Width">
              <input
                type="number"
                value={el.width}
                onChange={(e) => {
                  const v = num(e.target.value);
                  if (Number.isFinite(v) && v > 0) onUpdateElement(el.id, { width: v });
                }}
                className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
              />
            </Field>
            <Field label="Height">
              <input
                type="number"
                value={el.height}
                onChange={(e) => {
                  const v = num(e.target.value);
                  if (Number.isFinite(v) && v > 0) onUpdateElement(el.id, { height: v });
                }}
                className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
              />
            </Field>
            <Field label="Radius">
              <input
                type="number"
                min={0}
                value={el.rx ?? 0}
                onChange={(e) => {
                  const v = Math.max(0, num(e.target.value) || 0);
                  onUpdateElement(el.id, { rx: v, ry: v });
                }}
                className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
              />
            </Field>
          </Section>
        </>
      );
    }

    if (el.type === 'circle') {
      return (
        <>
          <Section title="Fill">
            <FillControls element={el} onUpdateElement={onUpdateElement} styleKey="fill" />
          </Section>
          <Section title="Geometry">
            <Field label="Radius">
              <input
                type="number"
                min={1}
                value={el.radius}
                onChange={(e) => {
                  const v = num(e.target.value);
                  if (Number.isFinite(v) && v > 0) onUpdateElement(el.id, { radius: v });
                }}
                className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
              />
            </Field>
          </Section>
        </>
      );
    }

    if (el.type === 'ellipse') {
      return (
        <>
          <Section title="Fill">
            <FillControls element={el} onUpdateElement={onUpdateElement} styleKey="fill" />
          </Section>
          <Section title="Geometry">
            <Field label="RX">
              <input
                type="number"
                min={1}
                value={el.rx}
                onChange={(e) => {
                  const v = num(e.target.value);
                  if (Number.isFinite(v) && v > 0) onUpdateElement(el.id, { rx: v });
                }}
                className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
              />
            </Field>
            <Field label="RY">
              <input
                type="number"
                min={1}
                value={el.ry}
                onChange={(e) => {
                  const v = num(e.target.value);
                  if (Number.isFinite(v) && v > 0) onUpdateElement(el.id, { ry: v });
                }}
                className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
              />
            </Field>
          </Section>
        </>
      );
    }

    if (el.type === 'line') {
      return (
        <>
          <Section title="Stroke">
            <FillControls element={el} onUpdateElement={onUpdateElement} styleKey="stroke" />
            <Field label="Width">
              <input
                type="number"
                min={1}
                value={el.strokeWidth ?? 1}
                onChange={(e) => {
                  const v = num(e.target.value);
                  if (Number.isFinite(v) && v > 0) onUpdateElement(el.id, { strokeWidth: v });
                }}
                className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
              />
            </Field>
          </Section>
        </>
      );
    }

    if (el.type === 'vector') {
      return (
        <>
          <Section title="Fill">
            <FillControls element={el} onUpdateElement={onUpdateElement} styleKey="fill" />
          </Section>
          <Section title="Geometry">
            <Field label="Width">
              <input
                type="number"
                min={1}
                value={Math.round(el.width)}
                onChange={(e) => {
                  const v = num(e.target.value);
                  if (Number.isFinite(v) && v > 0) onUpdateElement(el.id, { width: v });
                }}
                className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
              />
            </Field>
            <Field label="Height">
              <input
                type="number"
                min={1}
                value={Math.round(el.height)}
                onChange={(e) => {
                  const v = num(e.target.value);
                  if (Number.isFinite(v) && v > 0) onUpdateElement(el.id, { height: v });
                }}
                className="h-7 w-[72px] rounded-md border border-bordered bg-raised px-2 text-right font-mono text-[12px] focus:border-bordered-strong focus:outline-none"
              />
            </Field>
          </Section>
          <Section title="Path">
            <textarea
              value={el.path}
              rows={4}
              spellCheck={false}
              onChange={(e) => onUpdateElement(el.id, { path: e.target.value })}
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

    if (el.type === 'image') {
      return <ImageControls element={el} onUpdateElement={onUpdateElement} />;
    }

    return (
      <Section title="Fill">
        <FillControls element={el} onUpdateElement={onUpdateElement} styleKey="fill" />
      </Section>
    );
  }

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
      {!multi && primary ? renderSingle(primary) : (
        <p className="px-3 py-4 text-[12px] text-secondary">
          {selected.length} elements selected. Use the toolbar for align and
          distribute.
        </p>
      )}
      {!multi && primary && transformOn(primary)}
    </aside>
  );
}

function FillControls({
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

// -- image layer tools (v0.6 backlog) ----------------------------------------

function ImageControls({
  element,
  onUpdateElement,
}: {
  element: Extract<SceneGraphElement, { type: 'image' }>;
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
}) {
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const filters = element.filters ?? {};

  const setFilter = (
    key: 'brightness' | 'contrast' | 'saturation' | 'grayscale' | 'invert' | 'blur',
    value: number | boolean,
  ) => onUpdateElement(element.id, { filters: { ...filters, [key]: value } } as Partial<SceneGraphElement>);

  async function handleRemoveBackground() {
    setRemoving(true);
    setRemoveError(null);
    try {
      const { removeBackground } = await import('@/lib/api');
      const { resolveSrc } = await import('@/lib/editor/scene-fabric');
      const blob = await (await fetch(resolveSrc(element.src))).blob();
      const result = await removeBackground(blob);
      onUpdateElement(element.id, {
        src: result.url,
        width: result.width,
        height: result.height,
        filters: undefined,
      } as Partial<SceneGraphElement>);
    } catch (e) {
      setRemoveError(e instanceof Error ? e.message : 'Background removal failed.');
    } finally {
      setRemoving(false);
    }
  }

  const slider = (label: string, key: 'brightness' | 'contrast' | 'saturation' | 'blur', min = -100, max = 100) => {
    const val = typeof filters[key] === 'number' ? (filters[key] as number) : 0;
    return (
      <Field label={label}>
        <input
          type="range"
          min={min}
          max={max}
          value={Math.round(val * 100)}
          onChange={(e) => setFilter(key, Number(e.target.value) / 100)}
          className="h-7 w-full accent-[var(--accent)]"
        />
      </Field>
    );
  };

  const toggle = (label: string, key: 'grayscale' | 'invert') => (
    <label className="mb-2 flex items-center justify-between gap-2 last:mb-0">
      <span className="w-16 shrink-0 text-[12px] text-secondary">{label}</span>
      <input
        type="checkbox"
        checked={Boolean(filters[key])}
        onChange={(e) => setFilter(key, e.target.checked)}
        className="h-4 w-4 accent-[var(--accent)]"
      />
    </label>
  );

  return (
    <>
      <Section title="Adjust">
        {slider('Brightness', 'brightness')}
        {slider('Contrast', 'contrast')}
        {slider('Saturation', 'saturation', -100, 100)}
        {slider('Blur', 'blur', 0, 20)}
        <div className="mt-1 flex items-center justify-between border-t border-bordered pt-2">
          {toggle('Grayscale', 'grayscale')}
          {toggle('Invert', 'invert')}
        </div>
        <button
          type="button"
          className="mt-2 h-7 rounded-md border border-bordered bg-raised px-2 text-[11px] font-medium text-secondary transition-colors hover:bg-raised"
          onClick={() => onUpdateElement(element.id, { filters: undefined } as Partial<SceneGraphElement>)}
        >
          Reset filters
        </button>
      </Section>
      <Section title="Background">
        <button
          type="button"
          className="h-8 w-full rounded-[8px] bg-accent text-[12px] font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
          onClick={() => void handleRemoveBackground()}
          disabled={removing}
          data-testid="remove-bg-btn"
        >
          {removing ? 'Removing…' : 'Remove background'}
        </button>
        {removeError && (
          <p className="mt-1 text-[11px] text-danger" role="alert">
            {removeError}
          </p>
        )}
        <p className="mt-1 text-[11px] text-muted">
          Approximate foreground cutout (OpenCV segmentation).
        </p>
      </Section>
    </>
  );
}

function CanvasProperties({
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

function normalizeHex(value: string): string {
  if (/^#[0-9a-fA-F]{6}$/.test(value)) return value;
  const v = value.replace('#', '');
  if (v.length === 3) {
    return `#${v.split('').map((c) => c + c).join('')}`;
  }
  return '#000000';
}