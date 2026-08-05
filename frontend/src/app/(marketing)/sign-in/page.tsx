import type { Metadata } from "next";

import { AuthPageShell } from "@/features/auth/components/auth-page-shell";
import { AuthPanel } from "@/features/auth/components/auth-panel";

export const metadata: Metadata = {
  title: "Sign In — SourceWise",
};

type SignInPageProps = {
  searchParams: Promise<{
    forgot?: string | string[];
    reset?: string | string[];
  }>;
};

export default async function SignInPage({ searchParams }: SignInPageProps) {
  const params = await searchParams;
  const resetSucceeded = params.reset === "success";
  const openForgotPassword = params.forgot === "true" && !resetSucceeded;

  return (
    <AuthPageShell>
      <AuthPanel
        defaultStep={openForgotPassword ? "forgot" : "auth"}
        defaultTab="signin"
        initialSuccessMessage={
          resetSucceeded
            ? "Your password has been reset. Sign in with your new password."
            : ""
        }
        titleAs="h1"
      />
    </AuthPageShell>
  );
}

