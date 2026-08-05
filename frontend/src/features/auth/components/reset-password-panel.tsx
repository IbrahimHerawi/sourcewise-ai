"use client";

import * as React from "react";
import { Loader2, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthHeader } from "@/features/auth/components/auth-panel";
import { validatePassword } from "@/features/auth/password-validation";
import {
  ApiError,
  api,
  clearAuthSession,
  getApiErrorMessage,
} from "@/lib/api";

type ResetPasswordPanelProps = {
  token: string | null;
};

const RESET_TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;

function getInitialTokenError(token: string | null): string {
  if (!token || !token.trim()) {
    return "This password reset link is missing its token.";
  }
  if (!RESET_TOKEN_PATTERN.test(token)) {
    return "This password reset link is malformed.";
  }
  return "";
}

export function ResetPasswordPanel({ token }: ResetPasswordPanelProps) {
  const router = useRouter();
  const [newPassword, setNewPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [passwordError, setPasswordError] = React.useState("");
  const [confirmError, setConfirmError] = React.useState("");
  const [apiError, setApiError] = React.useState("");
  const [tokenError, setTokenError] = React.useState(() => getInitialTokenError(token));
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setApiError("");
    setPasswordError("");
    setConfirmError("");

    if (!token) {
      setTokenError("This password reset link is missing its token.");
      return;
    }

    const validationError = validatePassword(newPassword);
    if (validationError) {
      setPasswordError(validationError);
      return;
    }
    if (newPassword !== confirmPassword) {
      setConfirmError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      await api.resetPassword(token, newPassword);
      clearAuthSession();
      router.replace("/sign-in?reset=success");
    } catch (error: unknown) {
      if (
        error instanceof ApiError &&
        error.code === "invalid_password_reset_token"
      ) {
        setTokenError(
          "This password reset link is invalid, expired, or has already been used.",
        );
      } else if (error instanceof ApiError && error.code === "validation_error") {
        setPasswordError(
          getApiErrorMessage(
            error,
            "Your password does not meet the password requirements.",
          ),
        );
      } else {
        setApiError(
          getApiErrorMessage(
            error,
            "Unable to reset your password. Please try again.",
          ),
        );
      }
    } finally {
      setLoading(false);
    }
  };

  if (tokenError) {
    return (
      <div className="relative overflow-hidden rounded-lg p-6 text-center sm:p-8">
        <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/10">
          <XCircle className="size-7 text-destructive" />
        </div>
        <h1 className="text-xl leading-none tracking-tight" style={{ fontWeight: 450 }}>
          Reset link unavailable
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">{tokenError}</p>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Request a new link to continue.
        </p>
        <Button
          className="mt-6 h-11 w-full bg-brand-gradient text-sm font-medium hover:opacity-95"
          onClick={() => router.replace("/sign-in?forgot=true")}
          type="button"
        >
          Request a new link
        </Button>
        <Button
          className="mt-2 w-full"
          onClick={() => router.replace("/sign-in")}
          type="button"
          variant="ghost"
        >
          Back to Sign In
        </Button>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-lg p-6 sm:p-8">
      <AuthHeader
        description="Choose a strong new password for your SourceWise account."
        title="Create a new password"
        titleAs="h1"
      />

      <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <Label htmlFor="newPassword">New Password</Label>
          <Input
            id="newPassword"
            type="password"
            placeholder="••••••••"
            required
            autoComplete="new-password"
            autoFocus
            value={newPassword}
            onChange={(event) => {
              const value = event.target.value;
              setNewPassword(value);
              if (passwordError) setPasswordError("");
              if (confirmPassword && value !== confirmPassword) {
                setConfirmError("Passwords do not match");
              } else if (confirmError) {
                setConfirmError("");
              }
            }}
            aria-invalid={Boolean(passwordError)}
            aria-describedby={passwordError ? "new-password-error" : "password-requirements"}
            className={
              passwordError
                ? "auth-input border-destructive bg-muted"
                : "auth-input border-border bg-muted"
            }
          />
          {passwordError ? (
            <p id="new-password-error" className="text-xs text-destructive">
              {passwordError}
            </p>
          ) : (
            <p id="password-requirements" className="text-xs leading-5 text-muted-foreground">
              At least 12 characters with uppercase, lowercase, a number, and a symbol.
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="confirmNewPassword">Confirm New Password</Label>
          <Input
            id="confirmNewPassword"
            type="password"
            placeholder="••••••••"
            required
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => {
              const value = event.target.value;
              setConfirmPassword(value);
              setConfirmError(
                value && value !== newPassword ? "Passwords do not match" : "",
              );
            }}
            aria-invalid={Boolean(confirmError)}
            aria-describedby={confirmError ? "confirm-new-password-error" : undefined}
            className={
              confirmError
                ? "auth-input border-destructive bg-muted"
                : "auth-input border-border bg-muted"
            }
          />
          {confirmError && (
            <p id="confirm-new-password-error" className="text-xs text-destructive">
              {confirmError}
            </p>
          )}
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
          disabled={loading || Boolean(passwordError) || Boolean(confirmError)}
          type="submit"
        >
          {loading && <Loader2 className="size-4 animate-spin" />}
          {loading ? "Resetting…" : "Reset password"}
        </Button>
      </form>
    </div>
  );
}

