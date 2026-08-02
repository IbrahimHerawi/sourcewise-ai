import { notFound } from "next/navigation";
import { CollectionDetailPage } from "@/features/collections/components/detail/collection-detail-page";
import { DashboardShell } from "@/features/dashboard/components/dashboard-shell";
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
    <DashboardShell>
      <CollectionDetailPage
        collectionId={collectionId}
        initialPreview={parseCollectionDetailPreview(firstValue(query.state), tab)}
      />
    </DashboardShell>
  );
}
