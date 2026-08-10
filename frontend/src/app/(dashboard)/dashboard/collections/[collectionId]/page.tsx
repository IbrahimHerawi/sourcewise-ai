import { CollectionDetailPage } from "@/features/collections/components/detail/collection-detail-page";
import { parseCollectionDetailTab } from "@/features/collections/collection-detail-types";

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
  return (
    <CollectionDetailPage
      collectionId={collectionId}
      initialTab={tab}
    />
  );
}
