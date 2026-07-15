"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { Inter } from "next/font/google";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { DashboardSidebar } from "@/features/dashboard/components/dashboard-sidebar";
import styles from "./layout.module.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted">
        <div className="text-center space-y-3">
          <Loader2 className="mx-auto size-8 animate-spin text-brand" />
          <p className="text-sm text-muted-foreground font-medium">Loading workspace...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className={`${styles.shell} ${inter.variable}`} data-dashboard-shell>
      <DashboardSidebar />
      <main className={styles.content}>{children}</main>
    </div>
  );
}
