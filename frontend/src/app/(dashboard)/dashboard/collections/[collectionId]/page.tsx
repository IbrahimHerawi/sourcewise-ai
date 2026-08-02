import { CollectionDetailPage } from "@/features/collections/components/detail/collection-detail-page";
import {
  parseCollectionDetailPreview,
  parseCollectionDetailTab,
} from "@/features/collections/mock-collection-detail";

type CollectionDetailRouteProps = {
  params: Promise<{ collectionId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function firstValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function CollectionDetailRoute({
  params,
  searchParams,
}: CollectionDetailRouteProps) {
  const [{ collectionId }, query] = await Promise.all([params, searchParams]);
  const tab = parseCollectionDetailTab(firstValue(query.tab));
  const previewValue =
    process.env.NODE_ENV === "production" ? undefined : firstValue(query.state);

  return (
    <CollectionDetailPage
      collectionId={collectionId}
      initialPreview={parseCollectionDetailPreview(previewValue, tab)}
    />
  );
}
