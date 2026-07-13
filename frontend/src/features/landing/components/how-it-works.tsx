"use client";

import * as React from "react";
import { Typewriter } from "./typewriter";

const STEPS = [
  {
    num: "01",
    title: "Upload your documents",
    desc: "Drag & drop PDF, Markdown, or TXT files. SourceWise parses, chunks, and indexes every page in seconds — no setup required.",
  },
  {
    num: "02",
    title: "Ask any question",
    desc: "Type your question in plain language. Ask across a single file or your entire library — the AI understands context and intent.",
  },
  {
    num: "03",
    title: "Get grounded answers",
    desc: "Receive precise answers drawn only from your documents — with inline citations pointing back to the exact source passage.",
  },
];

/**
 * VisualPlaceholder
 * A clean, large rounded rectangle standing in for a future product screenshot.
 * Swap the inner markup (or replace with an <img>) when real visuals are ready.
 */
function VisualPlaceholder({ label }: { label: string }) {
  return (
    <div
      className="relative flex w-full max-w-[560px] aspect-[560/690] items-center justify-center overflow-hidden rounded-[32px] border border-border bg-muted"
      aria-label={`${label} preview placeholder`}
    >
      <div className="absolute inset-0 p-8 flex flex-col gap-5 opacity-[0.55]">
        <div className="flex items-center gap-2">
          <span className="size-2.5 rounded-full bg-border" />
          <span className="size-2.5 rounded-full bg-border" />
          <span className="size-2.5 rounded-full bg-border" />
        </div>
        <div className="mt-2 space-y-3">
          <div className="h-3 w-2/3 rounded-full bg-border" />
          <div className="h-3 w-1/2 rounded-full bg-border" />
        </div>
        <div className="mt-auto space-y-3">
          <div className="h-3 w-full rounded-full bg-border" />
          <div className="h-3 w-5/6 rounded-full bg-border" />
          <div className="h-3 w-4/6 rounded-full bg-border" />
        </div>
      </div>
      <span className="relative text-xs font-medium tracking-wide text-muted-foreground/70 uppercase">
        {label}
      </span>
    </div>
  );
}

/**
 * HowItWorks — a continuous overlapping sticky-stack scrollytelling.
 *
 * All step sections are `position: sticky; top: 0; height: 100vh`, stacked in
 * DOM order inside a tall container (N × 100vh). As the user scrolls:
 *   - Each section pins to the top when it reaches it.
 *   - The NEXT section scrolls up and OVER the current one (covering it),
 *     because it comes later in the DOM and has a solid white background.
 *   - During the transition, both sections are visible: the current one
 *     underneath, the next one sliding in from below.
 *
 * This is the "one slides out while the next slides in" effect — there is
 * NEVER empty space, because the next section is always physically entering
 * (covering) before the previous one is fully gone. No sequential wait.
 *
 * A subtle translateY + opacity on each section's inner content adds polish,
 * but the covering motion is what guarantees continuity. Animation affects
 * ONLY transform + opacity — never layout properties. Layout height never
 * collapses (each section is a stable 100vh).
 *
 * Respects prefers-reduced-motion (renders as a normal stacked list).
 */
export function HowItWorks() {
  const stackRef = React.useRef<HTMLDivElement>(null);
  const sectionsRef = React.useRef<Array<HTMLDivElement | null>>([]);
  const [reducedMotion, setReducedMotion] = React.useState(false);

  React.useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(mq.matches);
    update();
    mq.addEventListener?.("change", update);
    return () => mq.removeEventListener?.("change", update);
  }, []);

  React.useEffect(() => {
    if (reducedMotion) return;

    const sections = sectionsRef.current.filter(Boolean) as HTMLDivElement[];
    if (sections.length === 0) return;

    let raf = 0;
    let vh = window.innerHeight;
    const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

    const render = () => {
      // For each sticky section, compute how far it has been "covered" by the
      // next section. As the next section scrolls up over this one, this
      // section's content gently translates up + fades, while the incoming
      // section's content settles into place. Both are visible during the
      // overlap (the next section physically covers this one).
      for (let i = 0; i < sections.length; i++) {
        const section = sections[i];
        if (!section) continue;
        const rect = section.getBoundingClientRect();

        // `covered`: how much this section has been scrolled past (covered by
        // the next section). 0 = freshly pinned at top, 1 = fully scrolled past.
        const covered = clamp01(-rect.top / vh);

        // The covering motion is the PRIMARY effect: the next section (higher
        // z-index, solid white bg) physically scrolls up over this one. Both
        // are visible during the overlap. Opacity here only SOFTLY supports —
        // a section stays near full opacity while it's the topmost visible
        // one, dimming gently only as it gets covered. The LAST section never
        // gets covered, so it stays full opacity and holds.
        let translateY: number;
        let opacity: number;
        if (i === sections.length - 1) {
          // Last section: always full opacity; tiny settle-in offset.
          translateY = 0;
          opacity = 1;
        } else {
          // Non-last: drift up slightly + soft fade as the next section covers
          // it. Never fully transparent (the covering section hides it anyway).
          translateY = -30 * covered;
          opacity = 1 - covered * 0.5;
        }

        const content = section.querySelector<HTMLElement>("[data-step-content]");
        if (content) {
          content.style.transform = `translate3d(0, ${translateY.toFixed(2)}px, 0)`;
          content.style.opacity = opacity.toFixed(3);
          content.style.willChange = "transform, opacity";
        }
      }

      raf = 0;
    };

    const onScroll = () => {
      if (raf === 0) raf = requestAnimationFrame(render);
    };
    const onResize = () => {
      vh = window.innerHeight;
      onScroll();
    };

    render();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [reducedMotion]);

  return (
    <section id="how-it-works" className="bg-white">
      {/* Section header — left-aligned, 80% width, typewriter with persistent
          blinking caret. Top/bottom spacing balanced (top 20% larger than the
          previous value, bottom matches it). */}
      <div
        className="mx-auto max-w-[1280px]"
        style={{
          paddingTop: "clamp(96px, 13.2vw, 168px)",
          paddingBottom: "clamp(96px, 13.2vw, 168px)",
          paddingLeft: "clamp(20px, 3.3vw, 66px)",
          paddingRight: "clamp(20px, 3.3vw, 66px)",
        }}
      >
        <h2
          className="text-left tracking-tight text-foreground"
          style={{
            fontSize: "clamp(1.28rem, 3.92vw, 2.8rem)",
            fontWeight: 450,
            lineHeight: 1.1,
            maxWidth: "80%",
          }}
        >
          <Typewriter
            text="Your data, your answers, an AI platform that turns your documents into a single source of truth"
            persistentCaret
            caretColor="var(--brand, #497bf9)"
            reserveHeight
            startWhenVisible
            speed={37}
          />
        </h2>
      </div>

      {reducedMotion ? (
        // Reduced-motion: normal stacked list, no sticky/animation.
        <div
          className="mx-auto max-w-[1280px]"
          style={{
            marginTop: "clamp(60px, 8vw, 100px)",
            marginBottom: "clamp(80px, 11vw, 140px)",
            paddingLeft: "clamp(20px, 3.3vw, 66px)",
            paddingRight: "clamp(20px, 3.3vw, 66px)",
          }}
        >
          <div className="flex flex-col gap-[clamp(80px,11vw,140px)]">
            {STEPS.map((step) => (
              <StepPanel key={step.num} step={step} />
            ))}
          </div>
        </div>
      ) : (
        // Continuous overlapping sticky-stack. Container height = N × 100vh +
        // an extra 60vh "hold" buffer so the FINAL section stays pinned and
        // visible after it covers the previous one (no empty space at the end).
        // Each section is sticky top-0, height 100vh, solid white bg — the next
        // section physically slides up over the previous one. There is always
        // content filling the viewport during transitions (one slides out while
        // the next slides in), never empty space.
        <div ref={stackRef} style={{ height: `${STEPS.length * 100 + 60}vh` }}>
          {STEPS.map((step, i) => (
            <div
              key={step.num}
              ref={(el) => { sectionsRef.current[i] = el; }}
              className="sticky top-0 h-[100svh] w-full overflow-hidden bg-white"
              style={{ zIndex: i + 1 }}
            >
              <div
                data-step-content
                className="mx-auto flex h-full w-full max-w-[1280px] items-center"
                style={{
                  paddingLeft: "clamp(20px, 3.3vw, 66px)",
                  paddingRight: "clamp(20px, 3.3vw, 66px)",
                  willChange: "transform, opacity",
                }}
              >
                <StepPanel step={step} />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function StepPanel({ step }: { step: (typeof STEPS)[number] }) {
  // STRICT UNIFORM LAYOUT — no alternation:
  // LEFT = text content, RIGHT = image placeholder. Applies to all 3 sections.
  return (
    <div className="grid w-full items-center gap-[clamp(40px,7vw,110px)] lg:grid-cols-2">
      {/* Left: text content (heading + description) */}
      <div>
        <span className="block text-sm font-medium tabular-nums text-brand">
          {step.num}
        </span>
        <h3
          className="mt-5 text-foreground tracking-tight"
          style={{ fontSize: "clamp(2rem, 3.5vw, 42px)", fontWeight: 450, lineHeight: 1.12 }}
        >
          {step.title}
        </h3>
        <p
          className="mt-9 max-w-[520px] text-muted-foreground"
          style={{ fontSize: "clamp(1.05rem, 1.3vw, 1.25rem)", lineHeight: 1.7, fontWeight: 400 }}
        >
          {step.desc}
        </p>
      </div>

      {/* Right: image placeholder (same style for all sections, no variations) */}
      <div className="flex justify-end">
        <VisualPlaceholder label={`${step.title} preview`} />
      </div>
    </div>
  );
}
