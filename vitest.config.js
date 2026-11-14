import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// UI/component tests (jsdom + Testing Library + axe). The dependency-free
// Node tests in tests/web keep running under `npm run test:web`.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["tests/ui/**/*.test.{js,jsx}"],
    setupFiles: ["tests/ui/setup.js"],
    globals: true,
    css: false,
    testTimeout: 30000,
  },
});
