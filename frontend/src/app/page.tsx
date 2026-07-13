"use client";

import * as React from "react";
import { Navbar } from "@/components/landing/navbar";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { Features } from "@/components/landing/features";
import { Footer } from "@/components/landing/footer";
import { AuthDialog } from "@/components/landing/auth-dialog";
import { SmoothScroll } from "@/components/landing/smooth-scroll";

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
