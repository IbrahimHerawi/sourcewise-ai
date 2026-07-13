"use client";

import * as React from "react";
import { Navbar } from "@/features/landing/components/navbar";
import { Hero } from "@/features/landing/components/hero";
import { HowItWorks } from "@/features/landing/components/how-it-works";
import { Features } from "@/features/landing/components/features";
import { Footer } from "@/features/landing/components/footer";
import { AuthDialog } from "@/features/landing/components/auth-dialog";
import { SmoothScroll } from "@/features/landing/components/smooth-scroll";

export default function Home() {
  const [authOpen, setAuthOpen] = React.useState(false);
  const [authTab, setAuthTab] = React.useState<"signin" | "signup">("signin");

  const openAuth = React.useCallback((tab: "signin" | "signup") => {
    setAuthTab(tab);
    setAuthOpen(true);
  }, []);

  return (
    <SmoothScroll>
      <div className="relative flex min-h-[100svh] flex-col bg-background">
        <Navbar onOpenAuth={openAuth} />

        <main className="flex-1">
          <Hero onOpenAuth={openAuth} />
          <HowItWorks />
          <Features onOpenAuth={openAuth} />
        </main>

        <Footer />

        <AuthDialog open={authOpen} onOpenChange={setAuthOpen} defaultTab={authTab} />
      </div>
    </SmoothScroll>
  );
}
