"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { BrainCircuit, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { getApiErrorMessage } from "@/lib/api";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { verifyEmail } = useAuth();

  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const verificationRequest = useRef<{
    token: string;
    promise: Promise<void>;
  } | null>(null);

  const token = searchParams.get("token");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setErrorMessage("No verification token found in URL.");
      return;
    }

    const existingRequest = verificationRequest.current;
    const promise =
      existingRequest?.token === token
        ? existingRequest.promise
        : verifyEmail(token);

    if (existingRequest?.token !== token) {
      verificationRequest.current = { token, promise };
    }

    promise
      .then(() => {
        setStatus("success");
      })
      .catch((error: unknown) => {
        console.error("Verification error:", error);
        setStatus("error");
        setErrorMessage(
          getApiErrorMessage(error, "The verification token is invalid or expired."),
        );
      });
  }, [token, verifyEmail]);

  if (status === "loading") {
    return (
      <div className="text-center space-y-4">
        <Loader2 className="size-10 animate-spin text-brand mx-auto" />
        <h2 className="text-lg font-medium text-foreground">Verifying your email...</h2>
        <p className="text-sm text-muted-foreground">Please wait while we confirm your email address.</p>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="text-center space-y-4">
        <CheckCircle2 className="mx-auto size-12 text-brand" />
        <h2 className="text-xl font-semibold text-foreground">Email Verified!</h2>
        <p className="text-sm text-muted-foreground">
          Your email address has been successfully verified. You can now log in to your workspace.
        </p>
        <Button onClick={() => router.push("/")} className="w-full bg-brand-gradient">
          Go to Sign In
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4 text-center">
      <XCircle className="mx-auto size-12 text-destructive" />
      <h2 className="text-xl font-semibold text-foreground">Verification Failed</h2>
      <p className="rounded bg-destructive/10 p-3 text-sm font-medium text-destructive">
        {errorMessage}
      </p>
      <Button onClick={() => router.push("/")} variant="outline" className="w-full">
        Back to Home
      </Button>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <div className="w-full max-w-md space-y-6 rounded-2xl border border-border bg-card p-6 shadow-lg sm:p-8">
        <div className="flex flex-col items-center space-y-2 text-center">
          <div className="mb-2 flex size-12 items-center justify-center rounded-xl bg-brand-gradient text-primary-foreground">
            <BrainCircuit className="size-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">SourceWise</h1>
        </div>
        <Suspense
          fallback={
            <div className="space-y-4 text-center">
              <Loader2 className="mx-auto size-10 animate-spin text-brand" />
              <h2 className="text-lg font-medium text-foreground">Loading...</h2>
            </div>
          }
        >
          <VerifyEmailContent />
        </Suspense>
      </div>
    </div>
  );
}
