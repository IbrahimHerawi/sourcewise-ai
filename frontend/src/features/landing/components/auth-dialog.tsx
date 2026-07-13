"use client";

import * as React from "react";
import { BrainCircuit, Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { stopScroll, startScroll } from "./smooth-scroll";

type AuthDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultTab?: "signin" | "signup";
};

export function AuthDialog({ open, onOpenChange, defaultTab = "signin" }: AuthDialogProps) {
  const { toast } = useToast();
  const [tab, setTab] = React.useState<"signin" | "signup">(defaultTab);
  const [loading, setLoading] = React.useState(false);
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [confirmError, setConfirmError] = React.useState("");

  React.useEffect(() => {
    if (open) {
      setTab(defaultTab);
      setEmail("");
      setPassword("");
      setConfirmPassword("");
      setConfirmError("");
    }
  }, [open, defaultTab]);

  // Reset all fields when switching between Sign In and Sign Up tabs so each
  // form always opens with empty inputs.
  const handleTabChange = (v: string) => {
    setTab(v as "signin" | "signup");
    setEmail("");
    setPassword("");
    setConfirmPassword("");
    setConfirmError("");
  };

  // Lock body scroll (and stop Lenis smooth-scroll) while the dialog is open
  // so the page behind the modal doesn't scroll.
  React.useEffect(() => {
    if (!open) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    stopScroll();
    return () => {
      document.body.style.overflow = prevOverflow;
      startScroll();
    };
  }, [open]);

  // Validate confirm password on change.
  const handleConfirmChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setConfirmPassword(val);
    if (val && val !== password) {
      setConfirmError("Passwords do not match");
    } else {
      setConfirmError("");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Sign Up: validate that passwords match before submitting.
    if (tab === "signup" && password !== confirmPassword) {
      setConfirmError("Passwords do not match");
      return;
    }

    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      onOpenChange(false);
      setEmail("");
      setPassword("");
      setConfirmPassword("");
      setConfirmError("");
      toast({
        title: tab === "signup" ? "Account created" : "Welcome back",
        description:
          tab === "signup"
            ? "Your SourceWise workspace is ready. Launching the app…"
            : "Launching your SourceWise workspace…",
      });
    }, 1100);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-border bg-white p-0 sm:max-w-md">
        <div className="relative overflow-hidden rounded-lg">

          <div className="relative p-6 sm:p-8">
            <DialogHeader className="items-center text-center">
              <div className="mb-3 flex size-11 items-center justify-center rounded-xl bg-brand-gradient">
                <BrainCircuit className="size-6 text-white" />
              </div>
              <DialogTitle className="text-xl tracking-tight" style={{ fontWeight: 450 }}>
                {tab === "signup" ? "Create your account" : "Welcome back"}
              </DialogTitle>
              <DialogDescription>
                {tab === "signup"
                  ? "Start chatting with your documents in seconds."
                  : "Sign in to access your SourceWise workspace."}
              </DialogDescription>
            </DialogHeader>

            <Tabs value={tab} onValueChange={handleTabChange} className="mt-6">
              <TabsList className="grid w-full grid-cols-2 bg-muted">
                <TabsTrigger value="signin">Sign In</TabsTrigger>
                <TabsTrigger value="signup">Sign Up</TabsTrigger>
              </TabsList>

              <form onSubmit={handleSubmit} className="mt-5 space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@company.com"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="auth-input bg-muted border-border"
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password">Password</Label>
                    {tab === "signin" && (
                      <button
                        type="button"
                        className="text-xs text-brand-light hover:text-brand transition-colors"
                      >
                        Forgot?
                      </button>
                    )}
                  </div>
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    required
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      // Re-validate confirm field if it has a value.
                      if (confirmPassword && e.target.value !== confirmPassword) {
                        setConfirmError("Passwords do not match");
                      } else if (confirmError) {
                        setConfirmError("");
                      }
                    }}
                    className="auth-input bg-muted border-border"
                  />
                </div>

                {/* Confirm Password — only on Sign Up. Uses a CSS grid
                    0fr→1fr height transition for the modal expansion, plus
                    a fade + slide-up on the inner content for a polished
                    entrance. overflow-hidden only during collapse (signin);
                    visible when expanded (signup) so the input's focus
                    ring/border renders fully — no clipping. */}
                <div
                  className="grid transition-[grid-template-rows] duration-300 ease-out"
                  style={{
                    gridTemplateRows: tab === "signup" ? "1fr" : "0fr",
                  }}
                >
                  <div style={{ overflow: tab === "signup" ? "visible" : "hidden" }}>
                    <div
                      className="space-y-2 pb-4 transition-[opacity,transform] duration-300 ease-out"
                      style={{
                        opacity: tab === "signup" ? 1 : 0,
                        transform: tab === "signup" ? "translateY(0)" : "translateY(12px)",
                        transitionDelay: tab === "signup" ? "80ms" : "0ms",
                      }}
                    >
                      <Label htmlFor="confirmPassword">Confirm Password</Label>
                      <Input
                        id="confirmPassword"
                        type="password"
                        placeholder="••••••••"
                        required={tab === "signup"}
                        value={confirmPassword}
                        onChange={handleConfirmChange}
                        className={
                          confirmError
                            ? "auth-input bg-muted border-destructive"
                            : "auth-input bg-muted border-border"
                        }
                      />
                      {confirmError && (
                        <p className="text-xs text-destructive">{confirmError}</p>
                      )}
                    </div>
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={loading || (tab === "signup" && !!confirmError)}
                  className="w-full bg-brand-gradient h-11 text-sm font-medium hover:opacity-95"
                >
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  {loading
                    ? "Please wait…"
                    : tab === "signup"
                      ? "Create account"
                      : "Sign in"}
                </Button>
              </form>
            </Tabs>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
