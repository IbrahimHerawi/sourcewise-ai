import type { ReactNode } from "react";

export function AuthPageShell({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-[100svh] items-center justify-center bg-muted/30 p-4">
      <div className="w-full max-w-md overflow-hidden rounded-lg border border-border bg-card shadow-lg">
        {children}
      </div>
    </main>
  );
}

