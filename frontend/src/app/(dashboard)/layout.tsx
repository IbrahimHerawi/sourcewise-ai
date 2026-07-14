import type { ReactNode } from "react";
import { Inter } from "next/font/google";
import { DashboardSidebar } from "@/features/dashboard/components/dashboard-sidebar";
import styles from "./layout.module.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className={`${styles.shell} ${inter.variable}`}>
      <DashboardSidebar />
      <main className={styles.content}>{children}</main>
    </div>
  );
}
