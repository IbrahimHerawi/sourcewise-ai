const MIN_SCROLL_DURATION_MS = 900;
const MAX_SCROLL_DURATION_MS = 1400;

let cancelActiveScroll: (() => void) | null = null;

/**
 * Smoothstep with continuous acceleration at both ends. It keeps long page
 * moves easy to follow without the abrupt launch of a typical ease-out curve.
 */
function smootherStep(progress: number) {
  return progress * progress * progress * (progress * (progress * 6 - 15) + 10);
}

function scrollDuration(distance: number) {
  return Math.min(
    MAX_SCROLL_DURATION_MS,
    Math.max(MIN_SCROLL_DURATION_MS, 700 + Math.sqrt(distance) * 14),
  );
}

/**
 * Smoothly scrolls a header navigation click to an element while leaving all
 * direct scrolling in the browser's native input path.
 */
export function scrollFromHeaderNavigation(target: HTMLElement, offset: number) {
  cancelActiveScroll?.();

  const startY = window.scrollY;
  const maxY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
  const targetY = Math.min(
    maxY,
    Math.max(0, startY + target.getBoundingClientRect().top - offset),
  );
  const distance = Math.abs(targetY - startY);

  if (
    distance < 1 ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    window.scrollTo({ top: targetY, left: 0, behavior: "auto" });
    cancelActiveScroll = null;
    return;
  }

  const duration = scrollDuration(distance);
  let animationFrame = 0;
  let startTime: number | null = null;
  let cancelled = false;

  const interruptionEvents = ["wheel", "touchstart", "pointerdown"] as const;
  const scrollingKeys = new Set([
    "ArrowDown",
    "ArrowUp",
    "End",
    "Home",
    "PageDown",
    "PageUp",
    " ",
  ]);

  const removeInterruptionListeners = () => {
    interruptionEvents.forEach((eventName) => {
      window.removeEventListener(eventName, cancel);
    });
    window.removeEventListener("keydown", handleKeyDown);
  };

  const finish = () => {
    removeInterruptionListeners();
    if (cancelActiveScroll === cancel) cancelActiveScroll = null;
  };

  function cancel() {
    if (cancelled) return;
    cancelled = true;
    window.cancelAnimationFrame(animationFrame);
    finish();
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (scrollingKeys.has(event.key)) cancel();
  }

  const tick = (timestamp: number) => {
    if (cancelled) return;
    if (startTime === null) startTime = timestamp;

    const progress = Math.min(1, (timestamp - startTime) / duration);
    const nextY = startY + (targetY - startY) * smootherStep(progress);
    window.scrollTo({ top: nextY, left: 0, behavior: "auto" });

    if (progress < 1) {
      animationFrame = window.requestAnimationFrame(tick);
    } else {
      finish();
    }
  };

  interruptionEvents.forEach((eventName) => {
    window.addEventListener(eventName, cancel, { passive: true });
  });
  window.addEventListener("keydown", handleKeyDown);

  cancelActiveScroll = cancel;
  animationFrame = window.requestAnimationFrame(tick);
}
