import { AskQuestionScreen } from "@/features/questions/components/ask-question-screen";

type AskQuestionPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function AskQuestionPage({ searchParams }: AskQuestionPageProps) {
  const params = await searchParams;
  const value = Array.isArray(params.collectionId) ? params.collectionId[0] : params.collectionId;
  return <AskQuestionScreen initialCollectionId={value} />;
}
