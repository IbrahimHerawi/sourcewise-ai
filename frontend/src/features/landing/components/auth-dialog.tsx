"use client";

import * as React from "react";
import { BrainCircuit, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

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
import { useAuth } from "@/hooks/use-auth";
import { ApiError, getApiErrorMessage } from "@/lib/api";
import { stopScroll, startScroll } from "./smooth-scroll";

type AuthDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultTab?: "signin" | "signup";
};

function validatePassword(password: string): string | null {
  const hasLower = /[a-z]/.test(password);
  const hasUpper = /[A-Z]/.test(password);
  const hasDigit = /[0-9]/.test(password);
  const hasSymbol = /[^a-zA-Z0-9]/.test(password);
  const passwordBytes = new TextEncoder().encode(password);

  if (password.length < 12) {
    return "Password must be at least 12 characters.";
  }
  if (passwordBytes.length > 72) {
    return "Password must be at most 72 bytes.";
  }
  if (!hasLower || !hasUpper || !hasDigit || !hasSymbol) {
    return "Password must include uppercase, lowercase, number, and symbol characters.";
  }
  return null;
}

export function AuthDialog({ open, onOpenChange, defaultTab = "signin" }: AuthDialogProps) {
  const { toast } = useToast();
  const { login, resendVerification, signup } = useAuth();
  const router = useRouter();

  const [tab, setTab] = React.useState<"signin" | "signup">(defaultTab);
  const [loading, setLoading] = React.useState(false);
  const [firstName, setFirstName] = React.useState("");
  const [lastName, setLastName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [confirmError, setConfirmError] = React.useState("");
  const [passwordError, setPasswordError] = React.useState("");
  const [apiError, setApiError] = React.useState("");
  const [successMessage, setSuccessMessage] = React.useState("");
  const [verificationLink, setVerificationLink] = React.useState("");
  const [canResendVerification, setCanResendVerification] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setTab(defaultTab);
      setFirstName("");
      setLastName("");
      setEmail("");
      setPassword("");
      setConfirmPassword("");
      setConfirmError("");
      setPasswordError("");
      setApiError("");
      setSuccessMessage("");
      setVerificationLink("");
      setCanResendVerification(false);
    }
  }, [open, defaultTab]);

  const handleTabChange = (v: string) => {
    setTab(v as "signin" | "signup");
    setFirstName("");
    setLastName("");
    setEmail("");
    setPassword("");
    setConfirmPassword("");
    setConfirmError("");
    setPasswordError("");
    setApiError("");
    setSuccessMessage("");
    setVerificationLink("");
    setCanResendVerification(false);
  };

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

  const handleConfirmChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setConfirmPassword(val);
    if (val && val !== password) {
      setConfirmError("Passwords do not match");
    } else {
      setConfirmError("");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError("");
    setSuccessMessage("");
    setVerificationLink("");
    setPasswordError("");
    setConfirmError("");
    setCanResendVerification(false);

    if (tab === "signup") {
      const trimmedFirst = firstName.trim();
      const trimmedLast = lastName.trim();

      if (!trimmedFirst || !trimmedLast) {
        setApiError("First name and last name are required.");
        return;
      }

      if (trimmedFirst.length > 100 || trimmedLast.length > 100) {
        setApiError("First name and last name must be 100 characters or fewer.");
        return;
      }

      if (password !== confirmPassword) {
        setConfirmError("Passwords do not match");
        return;
      }

      const pwErr = validatePassword(password);
      if (pwErr) {
        setPasswordError(pwErr);
        return;
      }

      setLoading(true);
      try {
        const response = await signup(email.trim(), password, trimmedFirst, trimmedLast);
        const message = response.verification_token
          ? "Account created. Verify your email before signing in."
          : "Registration successful. Check your email to verify your account.";

        toast({
          title: "Account created",
          description: message,
        });

        setSuccessMessage(message);
        setVerificationLink(
          response.verification_token
            ? `/verify-email?token=${encodeURIComponent(response.verification_token)}`
            : "",
        );
        setTab("signin");
        setPassword("");
        setConfirmPassword("");
        setPasswordError("");
      } catch (error: unknown) {
        console.error("Registration error:", error);
        setApiError(
          error instanceof ApiError && error.code === "conflict"
            ? "An account with this email already exists. Try signing in instead."
            : getApiErrorMessage(error, "Registration failed."),
        );
      } finally {
        setLoading(false);
      }
    } else {
      setLoading(true);
      try {
        await login(email.trim(), password);
        toast({
          title: "Welcome back",
          description: "Launching your SourceWise workspace…",
        });
        onOpenChange(false);
        router.replace("/dashboard/documents");
      } catch (error: unknown) {
        console.error("Login error:", error);
        setCanResendVerification(
          error instanceof ApiError && error.code === "email_not_verified",
        );
        setApiError(getApiErrorMessage(error, "Invalid email or password."));
      } finally {
        setLoading(false);
      }
    }
  };

  const handleResendVerification = async () => {
    if (!email.trim()) {
      setApiError("Enter your email address before requesting another verification email.");
      return;
    }

    setLoading(true);
    setApiError("");
    try {
      const response = await resendVerification(email.trim());
      setSuccessMessage(response.message);
      setVerificationLink(
        response.verification_token
          ? `/verify-email?token=${encodeURIComponent(response.verification_token)}`
          : "",
      );
    } catch (error: unknown) {
      setApiError(getApiErrorMessage(error, "Unable to resend the verification email."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-border bg-card p-0 sm:max-w-md">
        <div className="relative overflow-hidden rounded-lg">
          <div className="relative p-6 sm:p-8">
            <DialogHeader className="items-center text-center">
              <div className="mb-3 flex size-11 items-center justify-center rounded-xl bg-brand-gradient">
                <BrainCircuit className="size-6 text-primary-foreground" />
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
                {tab === "signup" && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="firstName">First Name</Label>
                      <Input
                        id="firstName"
                        maxLength={100}
                        type="text"
                        placeholder="John"
                        required
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        className="auth-input bg-muted border-border"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="lastName">Last Name</Label>
                      <Input
                        id="lastName"
                        maxLength={100}
                        type="text"
                        placeholder="Doe"
                        required
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                        className="auth-input bg-muted border-border"
                      />
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    maxLength={320}
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
                  </div>
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    required
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (confirmPassword && e.target.value !== confirmPassword) {
                        setConfirmError("Passwords do not match");
                      } else if (confirmError) {
                        setConfirmError("");
                      }
                      if (passwordError) {
                        setPasswordError("");
                      }
                    }}
                    className={
                      passwordError
                        ? "auth-input bg-muted border-destructive"
                        : "auth-input bg-muted border-border"
                    }
                  />
                  {passwordError && (
                    <p className="text-xs text-destructive">{passwordError}</p>
                  )}
                </div>

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

                {apiError && (
                  <p
                    aria-live="assertive"
                    className="rounded bg-destructive/10 p-2 text-center text-xs font-medium text-destructive"
                  >
                    {apiError}
                  </p>
                )}

                {successMessage && (
                  <div
                    aria-live="polite"
                    className="space-y-2 rounded bg-primary/10 p-2 text-center text-xs font-medium text-primary"
                  >
                    <p>{successMessage}</p>
                    {verificationLink && (
                      <a className="underline underline-offset-2" href={verificationLink}>
                        Verify email now
                      </a>
                    )}
                  </div>
                )}

                {canResendVerification && (
                  <button
                    className="w-full text-xs text-brand underline underline-offset-2 disabled:opacity-50"
                    disabled={loading}
                    onClick={handleResendVerification}
                    type="button"
                  >
                    Resend verification email
                  </button>
                )}

                <Button
                  type="submit"
                  disabled={loading || (tab === "signup" && (!!confirmError || !!passwordError))}
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
