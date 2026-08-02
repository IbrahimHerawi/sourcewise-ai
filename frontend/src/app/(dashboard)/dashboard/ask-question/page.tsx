import { AskCollectionPage } from "@/features/collections/components/ask/ask-collection-page";

type AskQuestionPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AskQuestionPage({ searchParams }: AskQuestionPageProps) {
  const params = await searchParams;
  const value = Array.isArray(params.collectionId) ? params.collectionId[0] : params.collectionId;
  return <AskCollectionPage collectionId={value} />;
}
