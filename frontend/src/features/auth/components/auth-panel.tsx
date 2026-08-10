"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

import { BrandLogo } from "@/components/brand-logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/hooks/use-toast";
import { ApiError, api, getApiErrorMessage } from "@/lib/api";
import { validatePassword } from "@/features/auth/password-validation";

export type AuthTab = "signin" | "signup";
export type AuthStep = "auth" | "forgot";

type AuthPanelProps = {
  defaultStep?: AuthStep;
  defaultTab?: AuthTab;
  initialSuccessMessage?: string;
  onAuthenticated?: () => void;
  titleAs?: "h1" | "h2";
};

const transition = {
  duration: 0.28,
  ease: [0.22, 1, 0.36, 1] as const,
};

export function AuthHeader({
  description,
  title,
  titleAs: Title,
}: {
  description: string;
  title: string;
  titleAs: "h1" | "h2";
}) {
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <BrandLogo
        className="mb-3 size-11"
        sizes="44px"
        variant="mark"
      />
      <Title className="text-xl leading-none tracking-tight" style={{ fontWeight: 450 }}>
        {title}
      </Title>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

export function AuthPanel({
  defaultStep = "auth",
  defaultTab = "signin",
  initialSuccessMessage = "",
  onAuthenticated,
  titleAs = "h2",
}: AuthPanelProps) {
  const { toast } = useToast();
  const { login, resendVerification, signup } = useAuth();
  const router = useRouter();

  const [step, setStep] = React.useState<AuthStep | "confirmation">(defaultStep);
  const [tab, setTab] = React.useState<AuthTab>(defaultTab);
  const [loading, setLoading] = React.useState(false);
  const [firstName, setFirstName] = React.useState("");
  const [lastName, setLastName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [forgotEmail, setForgotEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [confirmError, setConfirmError] = React.useState("");
  const [passwordError, setPasswordError] = React.useState("");
  const [apiError, setApiError] = React.useState("");
  const [successMessage, setSuccessMessage] = React.useState(initialSuccessMessage);
  const [forgotConfirmation, setForgotConfirmation] = React.useState("");
  const [verificationLink, setVerificationLink] = React.useState("");
  const [canResendVerification, setCanResendVerification] = React.useState(false);

  React.useEffect(() => {
    setStep(defaultStep);
    setTab(defaultTab);
    setFirstName("");
    setLastName("");
    setEmail("");
    setForgotEmail("");
    setPassword("");
    setConfirmPassword("");
    setConfirmError("");
    setPasswordError("");
    setApiError("");
    setSuccessMessage(initialSuccessMessage);
    setForgotConfirmation("");
    setVerificationLink("");
    setCanResendVerification(false);
  }, [defaultStep, defaultTab, initialSuccessMessage]);

  const clearFeedback = () => {
    setApiError("");
    setSuccessMessage("");
    setVerificationLink("");
    setPasswordError("");
    setConfirmError("");
    setCanResendVerification(false);
  };

  const handleTabChange = (value: string) => {
    setTab(value as AuthTab);
    setFirstName("");
    setLastName("");
    setEmail("");
    setPassword("");
    setConfirmPassword("");
    clearFeedback();
  };

  const handleConfirmChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setConfirmPassword(value);
    setConfirmError(value && value !== password ? "Passwords do not match" : "");
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    clearFeedback();

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

      const validationError = validatePassword(password);
      if (validationError) {
        setPasswordError(validationError);
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
      return;
    }

    setLoading(true);
    try {
      await login(email.trim(), password);
      toast({
        title: "Welcome back",
        description: "Launching your SourceWise workspace…",
      });
      onAuthenticated?.();
      router.replace("/dashboard");
    } catch (error: unknown) {
      console.error("Login error:", error);
      setCanResendVerification(
        error instanceof ApiError && error.code === "email_not_verified",
      );
      setApiError(getApiErrorMessage(error, "Invalid email or password."));
    } finally {
      setLoading(false);
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

  const openForgotPassword = () => {
    setForgotEmail(email);
    clearFeedback();
    setStep("forgot");
  };

  const returnToSignIn = () => {
    setEmail(forgotEmail);
    setPassword("");
    setApiError("");
    setForgotConfirmation("");
    setTab("signin");
    setStep("auth");
  };

  const handleForgotPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setApiError("");
    setLoading(true);

    try {
      const response = await api.forgotPassword(forgotEmail.trim());
      setForgotConfirmation(response.message);
      setStep("confirmation");
    } catch (error: unknown) {
      setApiError(
        getApiErrorMessage(
          error,
          "Unable to send password reset instructions. Please try again.",
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      layout
      className="relative overflow-hidden rounded-lg"
      transition={transition}
    >
      <div className="relative p-6 sm:p-8">
        <AnimatePresence initial={false} mode="wait">
          {step === "auth" && (
            <motion.div
              key="auth"
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -16 }}
              initial={{ opacity: 0, x: -16 }}
              transition={transition}
            >
              <AuthHeader
                description={
                  tab === "signup"
                    ? "Start chatting with your documents in seconds."
                    : "Sign in to access your SourceWise workspace."
                }
                title={tab === "signup" ? "Create your account" : "Welcome back"}
                titleAs={titleAs}
              />

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
                          onChange={(event) => setFirstName(event.target.value)}
                          className="auth-input border-border bg-muted"
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
                          onChange={(event) => setLastName(event.target.value)}
                          className="auth-input border-border bg-muted"
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
                      autoComplete="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      className="auth-input border-border bg-muted"
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="password">Password</Label>
                      {tab === "signin" && (
                        <button
                          className="text-xs text-brand underline-offset-2 hover:underline focus-visible:underline focus-visible:outline-none"
                          onClick={openForgotPassword}
                          type="button"
                        >
                          Forgot password?
                        </button>
                      )}
                    </div>
                    <Input
                      id="password"
                      type="password"
                      placeholder="••••••••"
                      required
                      autoComplete={tab === "signup" ? "new-password" : "current-password"}
                      value={password}
                      onChange={(event) => {
                        setPassword(event.target.value);
                        if (confirmPassword && event.target.value !== confirmPassword) {
                          setConfirmError("Passwords do not match");
                        } else if (confirmError) {
                          setConfirmError("");
                        }
                        if (passwordError) {
                          setPasswordError("");
                        }
                      }}
                      aria-invalid={Boolean(passwordError)}
                      aria-describedby={passwordError ? "password-error" : undefined}
                      className={
                        passwordError
                          ? "auth-input border-destructive bg-muted"
                          : "auth-input border-border bg-muted"
                      }
                    />
                    {passwordError && (
                      <p id="password-error" className="text-xs text-destructive">
                        {passwordError}
                      </p>
                    )}
                  </div>

                  <div
                    className="grid transition-[grid-template-rows] duration-300 ease-out"
                    style={{ gridTemplateRows: tab === "signup" ? "1fr" : "0fr" }}
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
                          autoComplete="new-password"
                          value={confirmPassword}
                          onChange={handleConfirmChange}
                          aria-invalid={Boolean(confirmError)}
                          aria-describedby={confirmError ? "confirm-password-error" : undefined}
                          className={
                            confirmError
                              ? "auth-input border-destructive bg-muted"
                              : "auth-input border-border bg-muted"
                          }
                        />
                        {confirmError && (
                          <p id="confirm-password-error" className="text-xs text-destructive">
                            {confirmError}
                          </p>
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
                    disabled={
                      loading ||
                      (tab === "signup" && (Boolean(confirmError) || Boolean(passwordError)))
                    }
                    className="h-11 w-full bg-brand-gradient text-sm font-medium hover:opacity-95"
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
            </motion.div>
          )}

          {step === "forgot" && (
            <motion.div
              key="forgot"
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -16 }}
              initial={{ opacity: 0, x: 16 }}
              transition={transition}
            >
              <AuthHeader
                description="Enter your email and we’ll send you a secure reset link."
                title="Reset your password"
                titleAs={titleAs}
              />

              <form className="mt-6 space-y-4" onSubmit={handleForgotPassword}>
                <div className="space-y-2">
                  <Label htmlFor="forgotEmail">Email</Label>
                  <Input
                    id="forgotEmail"
                    maxLength={320}
                    type="email"
                    placeholder="you@company.com"
                    required
                    autoComplete="email"
                    autoFocus
                    value={forgotEmail}
                    onChange={(event) => {
                      setForgotEmail(event.target.value);
                      if (apiError) setApiError("");
                    }}
                    className="auth-input border-border bg-muted"
                  />
                </div>

                {apiError && (
                  <p
                    aria-live="assertive"
                    className="rounded bg-destructive/10 p-2 text-center text-xs font-medium text-destructive"
                  >
                    {apiError}
                  </p>
                )}

                <Button
                  className="h-11 w-full bg-brand-gradient text-sm font-medium hover:opacity-95"
                  disabled={loading}
                  type="submit"
                >
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  {loading ? "Sending…" : "Send reset link"}
                </Button>
                <Button
                  className="w-full"
                  disabled={loading}
                  onClick={returnToSignIn}
                  type="button"
                  variant="ghost"
                >
                  Back to Sign In
                </Button>
              </form>
            </motion.div>
          )}

          {step === "confirmation" && (
            <motion.div
              key="confirmation"
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              initial={{ opacity: 0, scale: 0.98 }}
              transition={transition}
              className="py-2 text-center"
            >
              <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-primary/10">
                <CheckCircle2 className="size-7 text-brand" />
              </div>
              <h2 className="text-xl leading-none tracking-tight" style={{ fontWeight: 450 }}>
                Check your email
              </h2>
              <p
                aria-live="polite"
                className="mt-3 text-sm leading-6 text-muted-foreground"
              >
                {forgotConfirmation}
              </p>
              <Button
                className="mt-6 h-11 w-full bg-brand-gradient text-sm font-medium hover:opacity-95"
                onClick={returnToSignIn}
                type="button"
              >
                OK
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
