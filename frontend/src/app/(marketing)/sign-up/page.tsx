import type { Metadata } from "next";

import { AuthPageShell } from "@/features/auth/components/auth-page-shell";
import { AuthPanel } from "@/features/auth/components/auth-panel";

export const metadata: Metadata = {
  title: "Sign Up — SourceWise",
};

export default function SignUpPage() {
  return (
    <AuthPageShell>
      <AuthPanel defaultTab="signup" titleAs="h1" />
    </AuthPageShell>
  );
}

