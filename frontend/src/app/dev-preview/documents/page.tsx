import { notFound } from "next/navigation";
import { DocumentsScreen } from "@/features/documents/components/documents-screen";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";

export default function DocumentsPreviewPage() {
  if (process.env.NODE_ENV !== "development") notFound();

  return (
    <DashboardShell>
      <DocumentsScreen />
    </DashboardShell>
  );
}
