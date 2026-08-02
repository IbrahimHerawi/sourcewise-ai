import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  css: {
    postcss: {
      plugins: [],
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "@test": fileURLToPath(new URL("./tests", import.meta.url)),
    },
  },
  test: {
    clearMocks: true,
    css: false,
    environment: "jsdom",
    environmentOptions: {
      jsdom: {
        url: "http://localhost:3000",
      },
    },
    exclude: ["tests/e2e/**", "node_modules/**", ".next/**"],
    include: [
      "src/**/__tests__/{unit,components,integration,pages}/**/*.test.{ts,tsx}",
      "tests/accessibility/**/*.test.{ts,tsx}",
    ],
    setupFiles: ["./tests/setup/vitest.setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.d.ts",
        "src/**/*.test.{ts,tsx}",
        "src/**/__tests__/**",
      ],
      reportsDirectory: "./coverage",
      reporter: ["text", "html", "lcov", "json-summary"],
    },
  },
});
