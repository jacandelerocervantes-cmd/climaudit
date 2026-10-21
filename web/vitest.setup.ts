import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach } from "vitest";

// Every test starts from the same stored settings (English, no persona).
beforeEach(() => {
  window.localStorage.setItem("cp.settings.v1", JSON.stringify({ language: "en" }));
});

afterEach(() => cleanup());
