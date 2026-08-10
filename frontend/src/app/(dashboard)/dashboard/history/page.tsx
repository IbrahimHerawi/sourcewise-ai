import { QuestionHistoryScreen } from "@/features/questions/components/question-history-screen";

type HistoryPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function HistoryPage({ searchParams }: HistoryPageProps) {
  const params = await searchParams;
  const pageValue = Array.isArray(params.page) ? params.page[0] : params.page;
  const parsedPage = Number.parseInt(pageValue ?? "1", 10);
  return <QuestionHistoryScreen initialPage={parsedPage > 0 ? parsedPage : 1} />;
}
