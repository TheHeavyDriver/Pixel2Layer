import { describe, it, expect } from "vitest";
import { formatDate, INPUT_CLASS_NAME } from "./utils";

describe("utils", () => {
  describe("formatDate", () => {
    it("formats ISO date to locale string", () => {
      const result = formatDate("2026-01-15T10:30:00Z");
      expect(result).toMatch(/Jan\s+15,\s+2026/);
    });

    it("handles different date formats", () => {
      const result = formatDate("2025-12-25T00:00:00Z");
      expect(result).toMatch(/Dec\s+25,\s+2025/);
    });
  });

  describe("INPUT_CLASS_NAME", () => {
    it("exports standard input class name", () => {
      expect(INPUT_CLASS_NAME).toContain("w-full");
      expect(INPUT_CLASS_NAME).toContain("rounded");
      expect(INPUT_CLASS_NAME).toContain("border");
    });
  });
});
