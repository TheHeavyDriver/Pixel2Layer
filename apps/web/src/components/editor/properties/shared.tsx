import { type ReactNode } from 'react';

export function Section({
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

export function Field({
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

export function normalizeHex(value: string): string {
  if (/^#[0-9a-fA-F]{6}$/.test(value)) return value;
  const v = value.replace('#', '');
  if (v.length === 3) {
    return `#${v.split('').map((c) => c + c).join('')}`;
  }
  return '#000000';
}

export const num = (v: string) => (v === '' ? NaN : Number(v));
