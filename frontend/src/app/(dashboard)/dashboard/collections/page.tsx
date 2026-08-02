import { CollectionsScreen } from "@/features/collections/components/collections-screen";
import {
  parseCollectionsModalPreview,
  parseCollectionsPreview,
} from "@/features/collections/mock-collections";

type CollectionsPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function CollectionsPage({ searchParams }: CollectionsPageProps) {
  const params = await searchParams;
  const state = Array.isArray(params.state) ? params.state[0] : params.state;
  const modal = Array.isArray(params.modal) ? params.modal[0] : params.modal;

  return (
    <CollectionsScreen
      initialModal={parseCollectionsModalPreview(modal)}
      initialPreview={parseCollectionsPreview(state)}
    />
  );
}
