import { notFound } from "next/navigation";
import dashboardStyles from "@/app/(dashboard)/layout.module.css";
import { CollectionDetailPage } from "@/features/collections/components/detail/collection-detail-page";
import { DashboardSidebar } from "@/features/dashboard/components/dashboard-sidebar";
import {
  parseCollectionDetailPreview,
  parseCollectionDetailTab,
} from "@/features/collections/mock-collection-detail";

type CollectionDetailPreviewRouteProps = {
  params: Promise<{ collectionId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function firstValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function CollectionDetailPreviewRoute({
  params,
  searchParams,
}: CollectionDetailPreviewRouteProps) {
  if (process.env.NODE_ENV === "production") notFound();

  const [{ collectionId }, query] = await Promise.all([params, searchParams]);
  const tab = parseCollectionDetailTab(firstValue(query.tab));

  return (
    <div className={dashboardStyles.shell}>
      <DashboardSidebar />
      <main className={dashboardStyles.content}>
        <CollectionDetailPage
          collectionId={collectionId}
          initialPreview={parseCollectionDetailPreview(firstValue(query.state), tab)}
        />
      </main>
    </div>
  );
}
