/**
 * Shared utility functions used across the application
 */

/**
 * Format ISO date string to locale date string
 * @param iso ISO 8601 date string
 * @returns Formatted date string (e.g., "Jan 15, 2026")
 */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * Standard input field class names for form inputs (Tailwind v4 design tokens)
 */
export const INPUT_CLASS_NAME =
  "h-10 w-full rounded-[10px] border border-bordered bg-raised px-3 text-[13px] text-primary outline-none transition-colors placeholder:text-muted focus:border-accent";
