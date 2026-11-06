'use client';

import { useState } from 'react';
import type { SceneGraphElement } from '@pixel2layer/schema';
import type { RegionsResult } from '@/lib/api';
import { extractErrorMessage } from '@/lib/error-utils';
import { Section, Field } from './shared';

export function ImageProperties({
  element,
  onUpdateElement,
}: {
  element: Extract<SceneGraphElement, { type: 'image' }>;
  onUpdateElement: (id: string, patch: Partial<SceneGraphElement>) => void;
}) {
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);
  const [regions, setRegions] = useState<RegionsResult | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [regionAction, setRegionAction] = useState<number | null>(null);
  const [regionError, setRegionError] = useState<string | null>(null);
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
      setRemoveError(extractErrorMessage(e, 'Background removal failed.'));
    } finally {
      setRemoving(false);
    }
  }

  async function currentBlob(): Promise<Blob> {
    const { resolveSrc } = await import('@/lib/editor/scene-fabric');
    const blob = await (await fetch(resolveSrc(element.src))).blob();
    return blob;
  }

  async function handleDetectRegions() {
    setDetecting(true);
    setRegionError(null);
    setRegions(null);
    try {
      const { detectRegions } = await import('@/lib/api');
      const blob = await currentBlob();
      setRegions(await detectRegions(blob));
    } catch (e) {
      setRegionError(extractErrorMessage(e, 'Region detection failed.'));
    } finally {
      setDetecting(false);
    }
  }

  async function applyRegionEdit(
    index: number,
    edit: 'crop' | 'keep' | 'remove',
  ) {
    setRegionAction(index);
    setRegionError(null);
    try {
      const { cropRegion, maskRegion } = await import('@/lib/api');
      const blob = await currentBlob();
      const result =
        edit === 'crop'
          ? await cropRegion(blob, index)
          : await maskRegion(blob, index, edit);
      onUpdateElement(element.id, {
        src: result.url,
        width: result.width,
        height: result.height,
        filters: undefined,
      } as Partial<SceneGraphElement>);
    } catch (e) {
      setRegionError(extractErrorMessage(e, 'Region edit failed.'));
    } finally {
      setRegionAction(null);
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
      <Section title="Regions">
        <button
          type="button"
          className="h-8 w-full rounded-[8px] border border-bordered bg-raised text-[12px] font-medium text-secondary transition-colors hover:bg-raised disabled:opacity-40"
          onClick={() => void handleDetectRegions()}
          disabled={detecting}
          data-testid="detect-regions-btn"
        >
          {detecting ? 'Detecting…' : regions ? 'Re-detect regions' : 'Detect regions'}
        </button>
        {regionError && (
          <p className="mt-1 text-[11px] text-danger" role="alert">
            {regionError}
          </p>
        )}
        {regions && regions.regions.length === 0 && (
          <p className="mt-1 text-[11px] text-muted">No foreground regions detected.</p>
        )}
        {regions && regions.regions.length > 0 && (
          <ul className="mt-2 space-y-1">
            {regions.regions.map((r, i) => (
              <li
                key={i}
                className="flex items-center justify-between gap-2 rounded-md border border-bordered bg-raised px-2 py-1"
              >
                <span className="min-w-0 truncate font-mono text-[11px] text-secondary">
                  #{i} · {r.width}×{r.height}
                </span>
                <span className="flex shrink-0 gap-1">
                  <button
                    type="button"
                    className="rounded px-1.5 py-0.5 text-[11px] font-medium text-secondary transition-colors hover:bg-bordered disabled:opacity-40"
                    onClick={() => void applyRegionEdit(i, 'crop')}
                    disabled={regionAction !== null}
                    data-testid={`region-crop-${i}`}
                  >
                    Crop
                  </button>
                  <button
                    type="button"
                    className="rounded px-1.5 py-0.5 text-[11px] font-medium text-secondary transition-colors hover:bg-bordered disabled:opacity-40"
                    onClick={() => void applyRegionEdit(i, 'keep')}
                    disabled={regionAction !== null}
                    data-testid={`region-keep-${i}`}
                  >
                    Keep
                  </button>
                  <button
                    type="button"
                    className="rounded px-1.5 py-0.5 text-[11px] font-medium text-secondary transition-colors hover:bg-bordered disabled:opacity-40"
                    onClick={() => void applyRegionEdit(i, 'remove')}
                    disabled={regionAction !== null}
                    data-testid={`region-remove-${i}`}
                  >
                    Cut
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-1 text-[11px] text-muted">
          Select a detected region to crop, keep, or cut out.
        </p>
      </Section>
    </>
  );
}
