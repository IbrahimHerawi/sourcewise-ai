"use client";

import * as React from "react";

/**
 * Official brand icons as inline SVGs (paths sourced from the brands' official
 * icon assets). Each icon is a single-color path that inherits `currentColor`,
 * so the hover color (the brand's official color) drives the fill.
 */

function GitHubIcon(props: React.SVGProps<SVGSVGElement>) {
  // Official GitHub octocat mark.
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  );
}

function LinkedInIcon(props: React.SVGProps<SVGSVGElement>) {
  // Official LinkedIn "in" mark.
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

function MailIcon(props: React.SVGProps<SVGSVGElement>) {
  // Standard filled envelope.
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M1.5 8.67v8.58a3 3 0 003 3h15a3 3 0 003-3V8.67l-8.928 5.493a3 3 0 01-3.144 0L1.5 8.67z" />
      <path d="M22.5 6.908V6.75a3 3 0 00-3-3h-15a3 3 0 00-3 3v.158l9.714 5.978a1.5 1.5 0 001.572 0L22.5 6.908z" />
    </svg>
  );
}

// Official brand colors.
const BRAND = {
  github: "#181717",
  linkedin: "#0A66C2",
  email: "#EA4335",
};

type SocialLink = {
  label: string;
  href: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  color: string;
};

const SOCIALS: SocialLink[] = [
  { label: "GitHub", href: "https://github.com", icon: GitHubIcon, color: BRAND.github },
  { label: "LinkedIn", href: "https://linkedin.com", icon: LinkedInIcon, color: BRAND.linkedin },
  { label: "Email", href: "mailto:hello@sourcewise.app", icon: MailIcon, color: BRAND.email },
];

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer id="footer" className="mt-auto bg-white">
      <div
        className="mx-auto max-w-[1280px] py-16"
        style={{ paddingLeft: "clamp(20px, 3.3vw, 66px)", paddingRight: "clamp(20px, 3.3vw, 66px)" }}
      >
        {/* Main: brand wordmark + tagline (About) and Contact links */}
        <div className="grid gap-12 md:grid-cols-2 md:gap-16">
          {/* About — large bold wordmark + light tagline */}
          <div>
            <a
              href="#top"
              className="tracking-tight text-foreground"
              style={{ fontSize: "clamp(2rem, 3.5vw, 42px)", fontWeight: 450, lineHeight: 1.12 }}
            >
              SourceWise
            </a>
            <p className="mt-4 max-w-sm text-base font-light leading-relaxed text-muted-foreground">
              Chat with your documents. Upload PDF, Markdown, and TXT files, then
              get AI answers grounded strictly in your content.
            </p>
          </div>

          {/* Contact — official brand icons, transparent background. On hover
              the icon adopts the brand color. Text stays the same size/weight
              in both states. Minimal and elegant — no dark chips, no overlays. */}
          <div className="md:justify-self-end">
            <ul className="space-y-3">
              {SOCIALS.map(({ label, href, icon: Icon, color }) => (
                <li key={label}>
                  <a
                    href={href}
                    {...(href.startsWith("mailto:") ? {} : { target: "_blank", rel: "noopener noreferrer" })}
                    className="group inline-flex items-center gap-3 text-base text-foreground transition-colors duration-200"
                    style={{ ["--brand" as string]: color }}
                  >
                    <Icon className="size-4 text-foreground transition-colors duration-200 group-hover:text-[var(--brand)]" />
                    <span>{label}</span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom bar — thin top border, small light copyright */}
        <div className="mt-14 border-t border-border pt-6">
          <p className="text-sm font-light text-muted-foreground">
            © {year} SourceWise. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
