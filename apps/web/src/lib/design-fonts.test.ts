import { describe, expect, it } from 'vitest';

import {
  DESIGN_FONT_FAMILIES,
  FONT_CATEGORY_LABELS,
  designFontListWith,
} from '@/lib/design-fonts';

describe('design font list', () => {
  it('covers all categories and keeps generic fallbacks', () => {
    expect(DESIGN_FONT_FAMILIES.length).toBeGreaterThan(20);
    const categories = new Set(DESIGN_FONT_FAMILIES.map((f) => f.category));
    expect([...categories].sort()).toEqual(['display', 'mono', 'sans', 'serif']);
    // generic CSS families come first and are always present
    expect(DESIGN_FONT_FAMILIES[0].family).toBe('sans-serif');
    for (const generic of ['sans-serif', 'serif', 'monospace']) {
      expect(DESIGN_FONT_FAMILIES.some((f) => f.family === generic)).toBe(true);
    }
  });

  it('maps categories to readable labels', () => {
    expect(FONT_CATEGORY_LABELS.sans).toBe('Sans-serif');
    expect(FONT_CATEGORY_LABELS.serif).toBe('Serif');
    expect(FONT_CATEGORY_LABELS.mono).toBe('Monospace');
    expect(FONT_CATEGORY_LABELS.display).toBe('Display');
  });

  it('contains fonts the API matcher can match', () => {
    for (const family of ['DejaVu Sans', 'Liberation Serif', 'Noto Sans Mono']) {
      expect(DESIGN_FONT_FAMILIES.some((f) => f.family === family)).toBe(true);
    }
  });

  it('keeps an existing family selectable even if unknown', () => {
    expect(designFontListWith('My Custom Font')[0].family).toBe('My Custom Font');
    expect(designFontListWith('My Custom Font').length).toBe(
      DESIGN_FONT_FAMILIES.length + 1,
    );
    // known families are not duplicated
    expect(designFontListWith('Arial').length).toBe(DESIGN_FONT_FAMILIES.length);
  });
});