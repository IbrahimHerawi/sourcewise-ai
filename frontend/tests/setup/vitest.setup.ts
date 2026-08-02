import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

const storageValues = new Map<string, string>();
const testLocalStorage: Storage = {
  get length() {
    return storageValues.size;
  },
  clear: () => storageValues.clear(),
  getItem: (key) => storageValues.get(key) ?? null,
  key: (index) => Array.from(storageValues.keys())[index] ?? null,
  removeItem: (key) => storageValues.delete(key),
  setItem: (key, value) => storageValues.set(key, String(value)),
};

Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: testLocalStorage,
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

Object.defineProperty(window, "matchMedia", {
  configurable: true,
  value: (query: string) => ({
    addEventListener: () => undefined,
    addListener: () => undefined,
    dispatchEvent: () => false,
    matches: false,
    media: query,
    onchange: null,
    removeEventListener: () => undefined,
    removeListener: () => undefined,
  }),
  writable: true,
});

Object.defineProperty(HTMLElement.prototype, "hasPointerCapture", {
  configurable: true,
  value: () => false,
});

Object.defineProperty(HTMLElement.prototype, "releasePointerCapture", {
  configurable: true,
  value: () => undefined,
});

Object.defineProperty(HTMLElement.prototype, "setPointerCapture", {
  configurable: true,
  value: () => undefined,
});

Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
  configurable: true,
  value: () => undefined,
});
