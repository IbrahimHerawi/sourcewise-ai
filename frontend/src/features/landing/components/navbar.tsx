"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { BrainCircuit, Menu, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { scrollToElement } from "./smooth-scroll";

const NAV_LINKS = [
  { label: "How It Works", href: "#how-it-works" },
  { label: "Features", href: "#features" },
  { label: "Contact", href: "#footer" },
];

const NAVBAR_HEIGHT = 52; // px — kept in sync with the min-height below

export function Navbar({ onOpenAuth }: { onOpenAuth: (tab: "signin" | "signup") => void }) {
  // "visible" = navbar is in view. Hides on scroll-down, shows on scroll-up.
  const [visible, setVisible] = React.useState(true);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const lastScrollY = React.useRef(0);
  const lastDir = React.useRef<"up" | "down" | null>(null);

  React.useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      const prev = lastScrollY.current;
      const delta = y - prev;

      // Pure direction-based logic — NO distance threshold.
      // Any downward scroll → hide immediately; any upward scroll → show
      // immediately. Works for slow/subtle scrolling too.
      if (y <= 0) {
        // Always show at the very top.
        setVisible(true);
        lastDir.current = null;
      } else if (delta > 0) {
        // Scrolling down (any amount) → hide.
        if (lastDir.current !== "down") {
          setVisible(false);
          lastDir.current = "down";
        }
      } else if (delta < 0) {
        // Scrolling up (any amount) → show.
        if (lastDir.current !== "up") {
          setVisible(true);
          lastDir.current = "up";
        }
      }
      lastScrollY.current = y;
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Keep the navbar visible when the mobile menu is open so users can close it.
  const showNavbar = visible || mobileOpen;

  const handleAuth = (tab: "signin" | "signup") => {
    setMobileOpen(false);
    onOpenAuth(tab);
  };

  // Smooth-scroll to the target section (e.g. the footer via "Contact").
  // Routed through Lenis when available for a fluid glide that matches the
  // site's smooth-scroll feel.
  const handleNavClick = (e: React.MouseEvent, href: string) => {
    const id = href.replace("#", "");
    const el = document.getElementById(id);
    if (el) {
      e.preventDefault();
      scrollToElement(el);
      setMobileOpen(false);
    }
  };

  return (
    <>
      <motion.header
        initial={{ y: -NAVBAR_HEIGHT, opacity: 0 }}
        animate={{
          y: showNavbar ? 0 : -NAVBAR_HEIGHT,
          opacity: showNavbar ? 1 : 0,
        }}
        transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        // Full-width, pinned flush to the very top.
        // Solid flat white background — no shadow, no border, no blur/overlay.
        className="fixed inset-x-0 top-0 z-50 w-full bg-white"
        style={{ willChange: "transform, opacity" }}
      >
        <nav
          className="mx-auto flex w-full max-w-7xl items-center gap-5 px-4 sm:px-6 lg:px-8"
          style={{ minHeight: `${NAVBAR_HEIGHT}px` }}
        >
          {/* Left cluster: brand + nav links, close together */}
          <a href="#top" className="group flex shrink-0 items-center gap-2.5">
            <span className="relative flex size-8 items-center justify-center rounded-lg bg-brand-gradient transition-transform group-hover:scale-105">
              <BrainCircuit className="size-5 text-white" />
            </span>
            <span className="text-base font-semibold tracking-tight">
              Source<span className="text-gradient-brand-strong">Wise</span>
            </span>
          </a>

          {/* Desktop nav — left-aligned, right after the brand */}
          <div className="hidden items-center gap-0.5 md:flex">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={(e) => handleNavClick(e, link.href)}
                className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* Spacer pushes actions to the right */}
          <div className="flex-1" />

          {/* Desktop actions — right-aligned */}
          <div className="hidden items-center gap-1.5 md:flex">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleAuth("signin")}
              className="h-8 px-3 text-sm text-muted-foreground hover:text-foreground"
            >
              Sign In
            </Button>
            <Button
              size="sm"
              onClick={() => handleAuth("signup")}
              className="bg-brand-gradient h-8 px-4 text-sm font-medium hover:opacity-95"
            >
              Sign Up
            </Button>
          </div>

          {/* Mobile toggle */}
          <button
            className="flex size-9 items-center justify-center rounded-md text-foreground md:hidden"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </nav>
      </motion.header>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 md:hidden"
            style={{ top: `${NAVBAR_HEIGHT}px` }}
          >
            <div
              className="absolute inset-0 bg-white"
              onClick={() => setMobileOpen(false)}
            />
            <motion.div
              initial={{ y: -16, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -16, opacity: 0 }}
              transition={{ duration: 0.25 }}
              // Solid white panel, no shadow — only a subtle border for separation.
              className="absolute inset-x-4 top-3 rounded-2xl border border-border bg-white p-4"
            >
              <div className="flex flex-col gap-1">
                {NAV_LINKS.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    onClick={(e) => handleNavClick(e, link.href)}
                    className="rounded-lg px-4 py-3 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
              <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
                <Button
                  variant="outline"
                  onClick={() => handleAuth("signin")}
                  className="border-border bg-muted/40"
                >
                  Sign In
                </Button>
                <Button
                  onClick={() => handleAuth("signup")}
                  className="bg-brand-gradient"
                >
                  Sign Up
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
