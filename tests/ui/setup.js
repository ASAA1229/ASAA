import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());

HTMLCanvasElement.prototype.getContext = () => null;

// jsdom does not implement these; the portal does not need them to function.
if (!window.matchMedia) {
  window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
}
