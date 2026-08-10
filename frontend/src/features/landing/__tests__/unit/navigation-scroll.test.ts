import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { scrollFromHeaderNavigation } from "@/features/landing/components/navigation-scroll";

describe("scrollFromHeaderNavigation", () => {
  let currentScrollY: number;
  let nextFrame: FrameRequestCallback | undefined;
  let scrollTo: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    currentScrollY = 100;
    nextFrame = undefined;
    scrollTo = vi.fn((options: ScrollToOptions) => {
      currentScrollY = options.top ?? currentScrollY;
    });

    Object.defineProperty(window, "scrollY", {
      configurable: true,
      get: () => currentScrollY,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 800,
    });
    Object.defineProperty(document.documentElement, "scrollHeight", {
      configurable: true,
      value: 3000,
    });
    Object.defineProperty(window, "scrollTo", {
      configurable: true,
      value: scrollTo,
    });
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      nextFrame = callback;
      return 1;
    });
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses a gradual animation and accounts for the fixed header", () => {
    const target = document.createElement("section");
    vi.spyOn(target, "getBoundingClientRect").mockReturnValue({
      bottom: 900,
      height: 200,
      left: 0,
      right: 100,
      top: 700,
      width: 100,
      x: 0,
      y: 700,
      toJSON: () => undefined,
    });

    scrollFromHeaderNavigation(target, 52);
    nextFrame?.(0);
    nextFrame?.(500);

    const halfwayY = scrollTo.mock.calls.at(-1)?.[0].top;
    expect(halfwayY).toBeGreaterThan(100);
    expect(halfwayY).toBeLessThan(748);

    nextFrame?.(2000);
    expect(scrollTo).toHaveBeenLastCalledWith({
      top: 748,
      left: 0,
      behavior: "auto",
    });
  });

  it("jumps immediately when reduced motion is preferred", () => {
    vi.spyOn(window, "matchMedia").mockReturnValue({
      addEventListener: vi.fn(),
      addListener: vi.fn(),
      dispatchEvent: vi.fn(),
      matches: true,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      removeEventListener: vi.fn(),
      removeListener: vi.fn(),
    });
    const target = document.createElement("section");
    vi.spyOn(target, "getBoundingClientRect").mockReturnValue({
      bottom: 900,
      height: 200,
      left: 0,
      right: 100,
      top: 700,
      width: 100,
      x: 0,
      y: 700,
      toJSON: () => undefined,
    });

    scrollFromHeaderNavigation(target, 52);

    expect(window.requestAnimationFrame).not.toHaveBeenCalled();
    expect(scrollTo).toHaveBeenCalledOnce();
    expect(scrollTo).toHaveBeenCalledWith({
      top: 748,
      left: 0,
      behavior: "auto",
    });
  });

  it("yields to direct wheel input", () => {
    const target = document.createElement("section");
    vi.spyOn(target, "getBoundingClientRect").mockReturnValue({
      bottom: 900,
      height: 200,
      left: 0,
      right: 100,
      top: 700,
      width: 100,
      x: 0,
      y: 700,
      toJSON: () => undefined,
    });

    scrollFromHeaderNavigation(target, 52);
    nextFrame?.(0);
    window.dispatchEvent(new WheelEvent("wheel"));
    const callsBeforeCancelledFrame = scrollTo.mock.calls.length;
    nextFrame?.(500);

    expect(window.cancelAnimationFrame).toHaveBeenCalled();
    expect(scrollTo).toHaveBeenCalledTimes(callsBeforeCancelledFrame);
  });
});
