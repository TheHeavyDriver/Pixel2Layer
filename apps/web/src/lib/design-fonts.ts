export type DesignFontCategory = 'sans' | 'serif' | 'mono' | 'display';

export interface DesignFontEntry {
  family: string;
  category: DesignFontCategory;
  generic: string;
}

/**
 * Curated font selection for the text properties panel.
 *
 * Mirrors the families the API font database can match during OCR
 * reconstruction (see apps/api/app/services/fonts/registry.py). Named families
 * fall back to whichever local font the browser substitutes; the generic
 * families always render.
 */
export const DESIGN_FONT_FAMILIES: DesignFontEntry[] = [
  // generic fallbacks first
  { family: 'sans-serif', category: 'sans', generic: 'sans-serif' },
  { family: 'serif', category: 'serif', generic: 'serif' },
  { family: 'monospace', category: 'mono', generic: 'monospace' },
  // sans-serif
  { family: 'Arial', category: 'sans', generic: 'sans-serif' },
  { family: 'DejaVu Sans', category: 'sans', generic: 'sans-serif' },
  { family: 'Liberation Sans', category: 'sans', generic: 'sans-serif' },
  { family: 'Open Sans', category: 'sans', generic: 'sans-serif' },
  { family: 'Fira Sans', category: 'sans', generic: 'sans-serif' },
  { family: 'Ubuntu', category: 'sans', generic: 'sans-serif' },
  { family: 'Noto Sans', category: 'sans', generic: 'sans-serif' },
  { family: 'Roboto', category: 'sans', generic: 'sans-serif' },
  { family: 'Lato', category: 'sans', generic: 'sans-serif' },
  { family: 'Montserrat', category: 'sans', generic: 'sans-serif' },
  { family: 'Source Sans 3', category: 'sans', generic: 'sans-serif' },
  { family: 'Inter', category: 'sans', generic: 'sans-serif' },
  { family: 'Nunito', category: 'sans', generic: 'sans-serif' },
  { family: 'Work Sans', category: 'sans', generic: 'sans-serif' },
  // serif
  { family: 'Georgia', category: 'serif', generic: 'serif' },
  { family: 'DejaVu Serif', category: 'serif', generic: 'serif' },
  { family: 'Liberation Serif', category: 'serif', generic: 'serif' },
  { family: 'Noto Serif', category: 'serif', generic: 'serif' },
  { family: 'Roboto Slab', category: 'serif', generic: 'serif' },
  { family: 'Merriweather', category: 'serif', generic: 'serif' },
  { family: 'Lora', category: 'serif', generic: 'serif' },
  { family: 'Playfair Display', category: 'serif', generic: 'serif' },
  // monospace
  { family: 'DejaVu Sans Mono', category: 'mono', generic: 'monospace' },
  { family: 'Liberation Mono', category: 'mono', generic: 'monospace' },
  { family: 'Fira Mono', category: 'mono', generic: 'monospace' },
  { family: 'Fira Code', category: 'mono', generic: 'monospace' },
  { family: 'Noto Sans Mono', category: 'mono', generic: 'monospace' },
  { family: 'Ubuntu Mono', category: 'mono', generic: 'monospace' },
  { family: 'Roboto Mono', category: 'mono', generic: 'monospace' },
  { family: 'JetBrains Mono', category: 'mono', generic: 'monospace' },
  { family: 'Source Code Pro', category: 'mono', generic: 'monospace' },
  // display / impact-style
  { family: 'Impact', category: 'display', generic: 'sans-serif' },
  { family: 'Oswald', category: 'display', generic: 'sans-serif' },
  { family: 'Bebas Neue', category: 'display', generic: 'sans-serif' },
  { family: 'Anton', category: 'display', generic: 'sans-serif' },
  { family: 'Poppins', category: 'display', generic: 'sans-serif' },
  { family: 'Bitter', category: 'display', generic: 'serif' },
  { family: 'Archivo Black', category: 'display', generic: 'sans-serif' },
];

export const FONT_CATEGORY_LABELS: Record<DesignFontCategory, string> = {
  sans: 'Sans-serif',
  serif: 'Serif',
  mono: 'Monospace',
  display: 'Display',
};

/** Ensures an arbitrary (e.g. API-matched) family is still selectable. */
export function designFontListWith(family: string | undefined): DesignFontEntry[] {
  if (!family || DESIGN_FONT_FAMILIES.some((f) => f.family === family)) {
    return DESIGN_FONT_FAMILIES;
  }
  return [{ family, category: 'sans', generic: 'sans-serif' }, ...DESIGN_FONT_FAMILIES];
}