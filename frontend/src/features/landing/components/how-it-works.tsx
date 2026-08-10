"use client";

import Image from "next/image";

import { Typewriter } from "./typewriter";

const STEPS = [
  {
    num: "01",
    title: "Upload your documents",
    desc: "Drag & drop PDF, Markdown, or TXT files. SourceWise parses, chunks, and indexes every page in seconds — no setup required.",
    image: "/images/how-it-works/upload-documents.png",
    imageAlt: "SourceWise document upload interface with a selected handbook file",
  },
  {
    num: "02",
    title: "Ask any question",
    desc: "Type your question in plain language. Ask across a single file or your entire library — the AI understands context and intent.",
    image: "/images/how-it-works/ask-question.png",
    imageAlt: "SourceWise question form asking who the company manager is",
  },
  {
    num: "03",
    title: "Get grounded answers",
    desc: "Receive precise answers drawn only from your documents — with inline citations pointing back to the exact source passage.",
    image: "/images/how-it-works/get-answer.png",
    imageAlt: "SourceWise grounded answer with two cited names",
  },
];

function ProductPreview({ src, alt }: { src: string; alt: string }) {
  return (
    <div
      className="relative aspect-square w-full max-w-[580px] overflow-hidden border border-border bg-muted"
      style={{ borderRadius: "clamp(24px, 2.66vw, 36px)" }}
    >
      <Image
        src={src}
        alt={alt}
        fill
        sizes="(min-width: 1352px) 580px, (min-width: 1024px) 43vw, (min-width: 640px) min(580px, calc(100vw - 64px)), calc(100vw - 32px)"
        className="object-cover"
      />
    </div>
  );
}

/**
 * A normal-flow, scroll-revealed product showcase. Rows stay in document flow
 * so the page-level scroll interpolation owns the complete feel. There are no
 * sticky locks, snap points, or section-specific scroll loops; fast input can
 * pass multiple rows and reverse immediately.
 */
export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-background">
      <div
        className="mx-auto max-w-[1352px] px-4 sm:px-[clamp(32px,5.33vw,72px)]"
        style={{
          paddingTop: "clamp(96px, 9vw, 120px)",
          paddingBottom: "clamp(80px, 9vw, 120px)",
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
            caretColor="var(--sw-color-brand-hover)"
            reserveHeight
            startWhenVisible
            speed={37}
          />
        </h2>
      </div>

      <div
        className="mx-auto max-w-[1352px] px-4 pb-[clamp(96px,9vw,120px)] sm:px-[clamp(32px,5.33vw,72px)]"
      >
        <div className="flex flex-col gap-20 lg:gap-6">
          {STEPS.map((step) => (
            <StepPanel key={step.num} step={step} />
          ))}
        </div>
      </div>
    </section>
  );
}

function StepPanel({ step }: { step: (typeof STEPS)[number] }) {
  return (
    <article className="grid w-full items-center gap-9 lg:grid-cols-[minmax(0,0.64fr)_minmax(0,1fr)] lg:gap-[clamp(56px,19vw,257px)]">
      <div className="text-center lg:text-left">
        <span className="block text-sm font-medium tabular-nums text-brand">
          {step.num}
        </span>
        <h3
          className="mt-3 text-foreground"
          style={{
            fontSize: "clamp(1.75rem, 3.1vw, 2.625rem)",
            fontWeight: 450,
            lineHeight: 1.04,
            letterSpacing: "-0.017em",
          }}
        >
          {step.title}
        </h3>
        <p
          className="mt-6 text-muted-foreground"
          style={{
            fontSize: "clamp(0.9375rem, 1.3vw, 1.09375rem)",
            lineHeight: "clamp(1.375rem, 1.88vw, 1.58625rem)",
            letterSpacing: "0.01em",
            fontWeight: 400,
          }}
          aria-label={step.desc}
        >
          <span aria-hidden="true">
            <Typewriter
              text={step.desc}
              reserveHeight
              startWhenVisible
              startDelay={0}
              speed={4}
              showCaret={false}
            />
          </span>
        </p>
      </div>

      <div className="flex justify-center lg:justify-end">
        <ProductPreview src={step.image} alt={step.imageAlt} />
      </div>
    </article>
  );
}
