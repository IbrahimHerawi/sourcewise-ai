import type { Metadata } from "next";

import { AuthPageShell } from "@/features/auth/components/auth-page-shell";
import { ResetPasswordPanel } from "@/features/auth/components/reset-password-panel";

export const metadata: Metadata = {
  title: "Reset Password — SourceWise",
};

type ResetPasswordPageProps = {
  searchParams: Promise<{
    token?: string | string[];
  }>;
};

export default async function ResetPasswordPage({
  searchParams,
}: ResetPasswordPageProps) {
  const params = await searchParams;
  const token = typeof params.token === "string" ? params.token : null;

  return (
    <AuthPageShell>
      <ResetPasswordPanel token={token} />
    </AuthPageShell>
  );
}

