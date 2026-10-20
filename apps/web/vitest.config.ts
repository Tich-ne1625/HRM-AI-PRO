import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    // Bound jsdom memory/CPU on local workstations and two-core CI runners.
    maxWorkers: 2,
    setupFiles: ["./src/test/setup.ts"],
  },
});

