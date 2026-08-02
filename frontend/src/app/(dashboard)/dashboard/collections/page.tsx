import { CollectionsScreen } from "@/features/collections/components/collections-screen";

type CollectionsPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function CollectionsPage({ searchParams }: CollectionsPageProps) {
  const params = await searchParams;
  const pageValue = Array.isArray(params.page) ? params.page[0] : params.page;
  const parsedPage = Number.parseInt(pageValue ?? "1", 10);
  return <CollectionsScreen initialPage={parsedPage > 0 ? parsedPage : 1} />;
}
