"use client";

import * as React from "react";

/**
 * Typewriter
 *
 * Reveals text one character at a time with a smooth, subtle feel and a soft
 * blinking caret while typing. Once complete, the caret fades out. Respects
 * prefers-reduced-motion (renders the full text immediately, no animation).
 *
 * Supports a single highlighted segment (rendered with a className) so part of
 * the text can be styled (e.g. a gradient) while still typing as one sentence.
 *
 * Usage:
 *   <Typewriter text="Chat with your documents Powered by AI"
 *              highlight="Powered by AI" highlightClassName="text-gradient-brand" />
 */
export function Typewriter({
  text,
  highlight,
  highlightClassName,
  speed = 55,
  startDelay = 350,
  className,
  style,
  breakBeforeHighlight = false,
  onDone,
  persistentCaret = false,
  caretColor,
  reserveHeight = false,
  startWhenVisible = false,
}: {
  text: string;
  highlight?: string;
  highlightClassName?: string;
  speed?: number;
  startDelay?: number;
  className?: string;
  style?: React.CSSProperties;
  breakBeforeHighlight?: boolean;
  onDone?: () => void;
  persistentCaret?: boolean;
  caretColor?: string;
  // When true, an invisible copy of the FULL text is rendered to reserve the
  // final height from the very first frame. The typed text is overlaid on top
  // (absolute). This prevents any layout shift as the text grows from 1 line
  // to N lines — the container is always full-height.
  reserveHeight?: boolean;
  // When true, the typing animation does NOT start on mount. It waits until
  // the element scrolls into the viewport (IntersectionObserver), then starts.
  startWhenVisible?: boolean;
}) {
  const rootRef = React.useRef<HTMLSpanElement>(null);
  const [inView, setInView] = React.useState(!startWhenVisible);
  const [count, setCount] = React.useState(0);
  const [done, setDone] = React.useState(false);
  const [reduced, setReduced] = React.useState(false);

  // Keep the latest onDone in a ref so the typing effect doesn't depend on its
  // identity. This prevents the effect from re-running (and restarting the
  // typing from scratch) when the parent re-renders and passes a new inline
  // onDone callback — which was causing the text to type twice.
  const onDoneRef = React.useRef(onDone);
  React.useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  React.useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener?.("change", update);
    return () => mq.removeEventListener?.("change", update);
  }, []);

  // Start typing only when `inView` is true (always true unless
  // startWhenVisible is set, in which case it flips when the element enters
  // the viewport via the IntersectionObserver below).
  React.useEffect(() => {
    if (!inView) return;
    if (reduced) {
      setCount(text.length);
      setDone(true);
      onDoneRef.current?.();
      return;
    }
    let i = 0;
    let timer: ReturnType<typeof setTimeout>;
    const startTimer = setTimeout(function tick() {
      i += 1;
      setCount(i);
      if (i < text.length) {
        timer = setTimeout(tick, speed);
      } else {
        setDone(true);
        onDoneRef.current?.();
      }
    }, startDelay);
    return () => {
      clearTimeout(startTimer);
      clearTimeout(timer!);
    };
  }, [text, speed, startDelay, reduced, inView]);

  // IntersectionObserver — flips `inView` to true the first time the element
  // enters the viewport, which kicks off the typing effect.
  React.useEffect(() => {
    if (!startWhenVisible || reduced) return;
    const el = rootRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setInView(true);
            io.disconnect();
            break;
          }
        }
      },
      { threshold: 0.25 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [startWhenVisible, reduced]);

  // Split the visible portion into: before-highlight, highlight (if within
  // the visible count), and after-highlight.
  const visible = text.slice(0, count);
  let before = visible;
  let highlighted = "";
  let after = "";

  if (highlight && text.includes(highlight)) {
    const hiStart = text.indexOf(highlight);
    const hiEnd = hiStart + highlight.length;
    if (count <= hiStart) {
      before = visible;
    } else if (count < hiEnd) {
      before = text.slice(0, hiStart);
      highlighted = text.slice(hiStart, count);
    } else {
      before = text.slice(0, hiStart);
      highlighted = highlight;
      after = text.slice(hiEnd, count);
    }
  }

  // The typed (visible) content — reused for both the normal and reserveHeight
  // rendering paths.
  const typedContent = (
    <>
      {before}
      {highlighted && (
        <>
          {breakBeforeHighlight && <br />}
          <span className={highlightClassName}>{highlighted}</span>
        </>
      )}
      {after}
      {/* Blinking caret. By default it fades out when typing is done; with
          persistentCaret it stays visible and keeps blinking indefinitely. */}
      <span
        aria-hidden="true"
        style={{
          display: "inline-block",
          width: "0.04em",
          marginLeft: "0.06em",
          height: "0.9em",
          verticalAlign: "-0.08em",
          backgroundColor: caretColor || "currentColor",
          opacity: done && !persistentCaret ? 0 : 1,
          transition: "opacity 400ms ease",
          animation: done && !persistentCaret ? "none" : "tw-caret 1s steps(1) infinite",
        }}
      />
    </>
  );

  if (reserveHeight) {
    // Reserve the FULL text height from the very first frame so the layout
    // never shifts as the text grows. An invisible copy of the full text
    // (including the highlight/break structure) reserves the height; the typed
    // text is overlaid absolutely on top. Both share the same font/width so
    // they wrap identically.
    const fullBefore = highlight && text.includes(highlight)
      ? text.slice(0, text.indexOf(highlight))
      : text;
    const fullHighlight = highlight && text.includes(highlight) ? highlight : "";
    const fullAfter = highlight && text.includes(highlight)
      ? text.slice(text.indexOf(highlight) + highlight.length)
      : "";

    return (
      <span ref={rootRef} className={className} style={{ ...style, position: "relative", display: "inline-block" }}>
        {/* Invisible full-text ghost — reserves the final height. */}
        <span aria-hidden="true" style={{ visibility: "hidden" }}>
          {fullBefore}
          {fullHighlight && (
            <>
              {breakBeforeHighlight && <br />}
              <span className={highlightClassName}>{fullHighlight}</span>
            </>
          )}
          {fullAfter}
        </span>
        {/* Typed text overlaid on top — same position, same wrapping. */}
        <span style={{ position: "absolute", inset: 0 }}>
          {typedContent}
        </span>
      </span>
    );
  }

  return (
    <span ref={rootRef} className={className} style={style}>
      {typedContent}
    </span>
  );
}
