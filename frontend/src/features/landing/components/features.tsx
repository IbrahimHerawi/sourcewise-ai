"use client";

import * as React from "react";
import { motion } from "framer-motion";

const ease = [0.22, 1, 0.36, 1] as const;

const FEATURES = [
  {
    title: "Multi-format support.",
    desc: "Drop in PDFs, Markdown, or plain-text files. SourceWise extracts and structures content from every format automatically.",
  },
  {
    title: "Grounded, hallucination-free.",
    desc: "Answers are drawn strictly from your documents. If it's not in your files, the AI says so, no made-up facts.",
  },
  {
    title: "Source citations.",
    desc: "Every response includes inline references linking back to the exact passage, so you can verify in a click.",
  },
  {
    title: "Lightning fast.",
    desc: "Documents are indexed the moment you upload. Get answers in milliseconds, even across hundreds of pages.",
  },
  {
    title: "Private and secure.",
    desc: "Your files are encrypted in transit and at rest. We never use your data to train models, it stays yours.",
  },
  {
    title: "Conversational context.",
    desc: "Ask follow-ups naturally. SourceWise remembers the thread, so each answer builds on the conversation.",
  },
];

export function Features({ onOpenAuth }: { onOpenAuth: (tab: "signin" | "signup") => void }) {
  return (
    <section
      id="features"
      className="relative bg-white"
      style={{ paddingTop: "clamp(96px, 13vw, 168px)", paddingBottom: "clamp(96px, 13vw, 168px)" }}
    >
      <div
        className="mx-auto max-w-[1280px]"
        style={{ paddingLeft: "clamp(20px, 3.3vw, 66px)", paddingRight: "clamp(20px, 3.3vw, 66px)" }}
      >
        {/* Header — left-aligned, heading occupies roughly the left third */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.7, ease }}
          className="max-w-xl"
        >
          <h2
            className="tracking-tight text-foreground"
            style={{ fontSize: "clamp(2rem, 3.5vw, 42px)", fontWeight: 450, lineHeight: 1.12 }}
          >
            Built for serious reading
          </h2>
          <p className="mt-4 text-pretty text-base text-muted-foreground sm:text-lg">
            A focused toolkit that turns dense documents into a conversation you can trust.
          </p>
        </motion.div>

        {/* Features grid — 3 columns × 2 rows. No cards, no borders, no
            shadows. Each feature is a two-tone vertical accent line (black
            top + light gray bottom) with the title and description inline.
            The accent line's left edge aligns with the heading's left edge. */}
        <div className="mt-24 grid gap-x-14 gap-y-20 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.6, ease, delay: (i % 3) * 0.08 }}
              className="flex gap-5"
            >
              {/* Two-tone vertical accent line. Very thin (1px), delicate.
                  Black top segment (~28px, crisp) with a small visible gap
                  before the light gray bottom segment. Both perfectly aligned
                  on the same vertical axis. The total height stretches to
                  match this feature's own content height (dynamic per item). */}
              <span
                aria-hidden="true"
                className="flex w-px shrink-0 flex-col self-stretch"
              >
                {/* Black top segment — fixed height, crisp, solid. */}
                <span
                  className="block w-full shrink-0"
                  style={{ height: "28px", backgroundColor: "#121317" }}
                />
                {/* Small visible gap between the two segments. */}
                <span className="block w-full shrink-0" style={{ height: "10px" }} />
                {/* Light gray bottom segment — fills the remaining height
                    dynamically, matching this feature's content. */}
                <span
                  className="block w-full flex-1"
                  style={{ backgroundColor: "#E6E6E6" }}
                />
              </span>

              {/* Title + description inline on the same line. Title ends with
                  a period, single space, then description continues. Title
                  stands out via weight (450) and slightly larger size. */}
              <p
                className="text-base text-muted-foreground"
                style={{ lineHeight: 1.75, fontWeight: 400 }}
              >
                <span style={{ fontWeight: 450, fontSize: "1.125rem" }} className="text-foreground">
                  {feature.title}
                </span>{" "}
                {feature.desc}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
