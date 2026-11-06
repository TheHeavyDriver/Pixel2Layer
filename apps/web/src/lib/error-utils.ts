/**
 * Extract a readable error message from an unknown error value.
 * Handles Error instances, strings, and fallback messages.
 */
export function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  return fallback;
}
