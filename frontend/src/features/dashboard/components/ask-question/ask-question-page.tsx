"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  AlertCircle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  FileText,
  Files,
  LoaderCircle,
  RotateCcw,
  Send,
  XCircle,
} from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/hooks/use-toast";
import {
  ApiError,
  api,
  getApiErrorMessage,
  type CitationResponse,
  type CollectionResponse,
  type DocumentSummaryResponse,
  type QuestionAnswerResponse,
} from "@/lib/api";
import type { QuestionViewState } from "@/features/dashboard/ask-question/types";

import styles from "./ask-question-page.module.css";

const ALL_DOCUMENTS_VALUE = "all";
const MAX_QUESTION_LENGTH = 4_000;
const DOCUMENT_PAGE_SIZE = 100;

type DocumentStatusSummary = {
  total: number;
  ready: number;
  pending: number;
  processing: number;
  failed: number;
};

function formatQuestionDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getQuestionErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 401) {
    return "Your session has expired. Sign in again to ask a question.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "Your account must be verified before asking questions.";
  }
  if (error instanceof ApiError && error.status === 404) {
    return "The selected collection is no longer available. Choose another collection.";
  }
  if (error instanceof ApiError && error.status >= 500) {
    return "The question-answering service is temporarily unavailable. Please try again.";
  }
  return getApiErrorMessage(error, fallback);
}

function getErrorStatus(error: unknown): number | null {
  return error instanceof ApiError ? error.status : null;
}

function summarizeDocuments(documents: readonly DocumentSummaryResponse[]): DocumentStatusSummary {
  return documents.reduce<DocumentStatusSummary>(
    (summary, document) => {
      summary.total += 1;
      if (document.status === "READY") summary.ready += 1;
      if (document.status === "PENDING") summary.pending += 1;
      if (document.status === "PROCESSING") summary.processing += 1;
      if (document.status === "FAILED") summary.failed += 1;
      return summary;
    },
    { total: 0, ready: 0, pending: 0, processing: 0, failed: 0 },
  );
}

function AnswerPanel({ response }: { response: QuestionAnswerResponse }) {
  const metadata = [
    formatQuestionDate(response.created_at),
    response.model,
    response.provider,
  ].filter((value): value is string => Boolean(value));

  return (
    <Card className={styles.answerCard}>
      <CardContent className={styles.answerContent}>
        <h2 className={styles.answerHeading}>
          <FileText aria-hidden="true" />
          Answer
        </h2>
        <p className={styles.answerText}>{response.answer}</p>
        <div className={styles.answerMeta}>
          {metadata.map((value, index) => (
            <span className={styles.answerMetaItem} key={`${value}-${index}`}>
              {index > 0 ? <span className={styles.metaSeparator}>·</span> : null}
              {value}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function CitationItem({ citation }: { citation: CitationResponse }) {
  return (
    <li className={styles.citation}>
      <div className={styles.citationHeader}>
        <span className={styles.citationRank}>#{citation.rank}</span>
        <span className={styles.citationName}>{citation.document_filename}</span>
      </div>
      <p className={styles.citationExcerpt}>{citation.excerpt}</p>
      <span className={styles.citationMetadata}>
        Chunk {citation.chunk_index + 1} · distance {citation.distance.toFixed(3)} · document {citation.document_id}
      </span>
    </li>
  );
}

function CitationsPanel({ citations }: { citations: readonly CitationResponse[] }) {
  if (citations.length === 0) {
    return (
      <Card className={styles.noCitationsCard}>
        <CardContent className={styles.noCitationsContent}>
          <Files aria-hidden="true" />
          <span>No citations were returned for this answer.</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Accordion className={styles.sourcesAccordion} collapsible type="single">
      <AccordionItem className={styles.sourcesItem} value="sources">
        <AccordionTrigger className={styles.sourcesTrigger}>
          <span className={styles.sourcesTriggerLabel}>
            <Files aria-hidden="true" />
            Sources ({citations.length})
          </span>
        </AccordionTrigger>
        <AccordionContent className={styles.sourcesContent}>
          <ol className={styles.citationList}>
            {citations.map((citation) => (
              <CitationItem citation={citation} key={`${citation.chunk_id}-${citation.rank}`} />
            ))}
          </ol>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

function LoadingAnswer() {
  return (
    <Card className={styles.loadingCard} aria-label="Generating answer" role="status">
      <Skeleton className={styles.loadingHeading} />
      <Skeleton className={styles.loadingLine} />
      <Skeleton className={styles.loadingLine} />
      <Skeleton className={styles.loadingLineShort} />
      <Skeleton className={styles.loadingMeta} />
    </Card>
  );
}

function ErrorState({
  actionLabel,
  message,
  onAction,
  title,
}: {
  actionLabel?: string;
  message: string;
  onAction?: () => void;
  title: string;
}) {
  return (
    <Alert className={styles.errorAlert} variant="destructive">
      <AlertCircle aria-hidden="true" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {actionLabel && onAction ? (
          <Button onClick={onAction} size="sm" type="button" variant="outline">
            {actionLabel}
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

function EmptyAnswerState() {
  return (
    <Card className={styles.emptyCard} role="status">
      <CardContent className={styles.emptyContent}>
        <CircleHelp aria-hidden="true" />
        <h2>Ask a question to get started</h2>
        <p>Your answer and source citations will appear here.</p>
      </CardContent>
    </Card>
  );
}

function DocumentReadiness({
  documents,
  error,
  errorStatus,
  isLoading,
  onSignIn,
  onRetry,
  selectedCollection,
}: {
  documents: readonly DocumentSummaryResponse[];
  error: string | null;
  errorStatus: number | null;
  isLoading: boolean;
  onSignIn: () => void;
  onRetry: () => void;
  selectedCollection: string;
}) {
  if (isLoading) {
    return (
      <div className={styles.readinessLoading} aria-label="Loading document readiness" role="status">
        <Skeleton className={styles.readinessSkeleton} />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        actionLabel={errorStatus === 401 ? "Sign in again" : "Retry"}
        message={error}
        onAction={errorStatus === 401 ? onSignIn : onRetry}
        title="Documents could not be loaded"
      />
    );
  }

  const summary = summarizeDocuments(documents);
  if (summary.total === 0) {
    return (
      <div className={styles.readinessEmpty} role="status">
        <Files aria-hidden="true" />
        <span>
          {selectedCollection === ALL_DOCUMENTS_VALUE
            ? "Upload a document before asking a question."
            : "This collection does not contain any documents."}
        </span>
        <Button asChild size="sm" type="button" variant="link">
          <Link href="/dashboard/documents">Manage documents</Link>
        </Button>
      </div>
    );
  }

  if (summary.ready === 0) {
    const pendingCount = summary.pending + summary.processing;
    const message = pendingCount > 0
      ? `${pendingCount} document${pendingCount === 1 ? " is" : "s are"} still processing. At least one document must be ready before you can ask a question.`
      : "No ready documents are available in this scope. Review failed documents in Documents.";

    return (
      <div className={styles.readinessBlocked} role="status">
        {pendingCount > 0 ? <Clock3 aria-hidden="true" /> : <XCircle aria-hidden="true" />}
        <span>{message}</span>
      </div>
    );
  }

  return (
    <div className={styles.readinessReady} role="status">
      <CheckCircle2 aria-hidden="true" />
      <span>
        {summary.ready} ready document{summary.ready === 1 ? "" : "s"} available
        {summary.pending + summary.processing > 0
          ? ` · ${summary.pending + summary.processing} still processing`
          : ""}
        {summary.failed > 0 ? ` · ${summary.failed} failed` : ""}
      </span>
    </div>
  );
}

export function AskQuestionPage() {
  const { logout } = useAuth();
  const { toast } = useToast();
  const [collections, setCollections] = useState<CollectionResponse[]>([]);
  const [selectedCollection, setSelectedCollection] = useState(ALL_DOCUMENTS_VALUE);
  const [documents, setDocuments] = useState<DocumentSummaryResponse[]>([]);
  const [isCollectionsLoading, setIsCollectionsLoading] = useState(true);
  const [collectionsError, setCollectionsError] = useState<string | null>(null);
  const [collectionsErrorStatus, setCollectionsErrorStatus] = useState<number | null>(null);
  const [isDocumentsLoading, setIsDocumentsLoading] = useState(true);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [documentsErrorStatus, setDocumentsErrorStatus] = useState<number | null>(null);
  const [collectionRetry, setCollectionRetry] = useState(0);
  const [documentsRetry, setDocumentsRetry] = useState(0);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<QuestionAnswerResponse | null>(null);
  const [questionState, setQuestionState] = useState<QuestionViewState>("idle");
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [submissionErrorStatus, setSubmissionErrorStatus] = useState<number | null>(null);
  const questionInputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadCollections() {
      setIsCollectionsLoading(true);
      setCollectionsError(null);
      setCollectionsErrorStatus(null);
      try {
        const response = await api.listCollections({ limit: DOCUMENT_PAGE_SIZE });
        if (isMounted) setCollections(response.items);
      } catch (error: unknown) {
        if (isMounted) {
          setCollectionsError(getQuestionErrorMessage(error, "Unable to load your collections."));
          setCollectionsErrorStatus(getErrorStatus(error));
        }
      } finally {
        if (isMounted) setIsCollectionsLoading(false);
      }
    }

    void loadCollections();
    return () => {
      isMounted = false;
    };
  }, [collectionRetry]);

  useEffect(() => {
    let isMounted = true;

    async function loadDocuments() {
      setIsDocumentsLoading(true);
      setDocumentsError(null);
      setDocumentsErrorStatus(null);
      try {
        const response = await api.listDocuments({
          limit: DOCUMENT_PAGE_SIZE,
          collectionId: selectedCollection === ALL_DOCUMENTS_VALUE ? undefined : selectedCollection,
        });
        if (isMounted) setDocuments(response.items);
      } catch (error: unknown) {
        if (isMounted) {
          setDocumentsError(getQuestionErrorMessage(error, "Unable to load documents for this scope."));
          setDocumentsErrorStatus(getErrorStatus(error));
        }
      } finally {
        if (isMounted) setIsDocumentsLoading(false);
      }
    }

    void loadDocuments();
    return () => {
      isMounted = false;
    };
  }, [documentsRetry, selectedCollection]);

  useEffect(() => {
    if (
      selectedCollection !== ALL_DOCUMENTS_VALUE &&
      collections.length > 0 &&
      !collections.some((collection) => collection.id === selectedCollection)
    ) {
      setSelectedCollection(ALL_DOCUMENTS_VALUE);
    }
  }, [collections, selectedCollection]);

  const readyDocumentCount = useMemo(
    () => documents.filter((document) => document.status === "READY").length,
    [documents],
  );
  const collectionScopeReady =
    selectedCollection === ALL_DOCUMENTS_VALUE || (!isCollectionsLoading && !collectionsError);
  const canAsk =
    question.trim().length > 0 &&
    questionState !== "loading" &&
    collectionScopeReady &&
    !isDocumentsLoading &&
    !documentsError &&
    readyDocumentCount > 0;

  function handleCollectionChange(value: string) {
    setSelectedCollection(value);
    setAnswer(null);
    setQuestionState("idle");
    setSubmissionError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canAsk) return;

    const trimmedQuestion = question.trim();
    setQuestionState("loading");
    setSubmissionError(null);
    setSubmissionErrorStatus(null);
    setAnswer(null);

    try {
      const response = await api.askQuestion({
        question: trimmedQuestion,
        collectionId: selectedCollection === ALL_DOCUMENTS_VALUE ? undefined : selectedCollection,
      });
      setAnswer(response);
      setQuestionState("success");
      toast({
        title: "Question answered",
        description: "The question and answer were saved to History.",
        variant: "success",
      });
    } catch (error: unknown) {
      setQuestionState("error");
      setSubmissionError(getQuestionErrorMessage(error, "Unable to answer this question."));
      setSubmissionErrorStatus(getErrorStatus(error));
    }
  }

  function handleReset() {
    setQuestion("");
    setAnswer(null);
    setQuestionState("idle");
    setSubmissionError(null);
    setSubmissionErrorStatus(null);
    window.requestAnimationFrame(() => questionInputRef.current?.focus());
  }

  return (
    <section className={styles.page} aria-labelledby="ask-question-heading">
      <div className={styles.content}>
        <header>
          <h1 className={styles.heading} id="ask-question-heading">
            Ask Your Documents
          </h1>
        </header>

        <form className={styles.composer} onSubmit={handleSubmit}>
          <Label className={styles.questionLabel} htmlFor="question-input">
            Your question
          </Label>
          <Textarea
            aria-describedby="question-help"
            aria-invalid={questionState === "error"}
            className={styles.questionInput}
            id="question-input"
            maxLength={MAX_QUESTION_LENGTH}
            onChange={(event) => {
              setQuestion(event.target.value);
              if (questionState === "error" || questionState === "success") {
                setQuestionState("idle");
                setSubmissionError(null);
                setAnswer(null);
              }
            }}
            placeholder="Ask a question about your documents..."
            ref={questionInputRef}
            rows={4}
            value={question}
          />
          <div className={styles.inputFooter}>
            <div className={styles.scopeGroup}>
              <span className={styles.scopeLabel}>Search in:</span>
              <Select
                disabled={isCollectionsLoading || Boolean(collectionsError)}
                onValueChange={handleCollectionChange}
                value={selectedCollection}
              >
                <SelectTrigger className={styles.scopeSelect} aria-label="Choose a question scope">
                  <SelectValue placeholder="Select a collection" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_DOCUMENTS_VALUE}>All documents</SelectItem>
                  {collections.map((collection) => (
                    <SelectItem key={collection.id} value={collection.id}>
                      {collection.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button className={styles.askButton} disabled={!canAsk} type="submit">
              {questionState === "loading" ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <Send aria-hidden="true" />
              )}
              {questionState === "loading" ? "Thinking..." : "Ask"}
            </Button>
          </div>
          <span className={styles.visuallyHidden} id="question-help">
            Enter a question up to {MAX_QUESTION_LENGTH.toLocaleString()} characters. Questions are answered using ready documents only.
          </span>

          {collectionsError ? (
            <ErrorState
              actionLabel={collectionsErrorStatus === 401 ? "Sign in again" : "Retry"}
              message={collectionsError}
              onAction={collectionsErrorStatus === 401 ? logout : () => setCollectionRetry((retry) => retry + 1)}
              title="Collections could not be loaded"
            />
          ) : null}

          <DocumentReadiness
            documents={documents}
            error={documentsError}
            errorStatus={documentsErrorStatus}
            isLoading={isDocumentsLoading}
            onSignIn={logout}
            onRetry={() => setDocumentsRetry((retry) => retry + 1)}
            selectedCollection={selectedCollection}
          />

          {submissionError ? (
            <ErrorState
              actionLabel={submissionErrorStatus === 401 ? "Sign in again" : undefined}
              message={submissionError}
              onAction={submissionErrorStatus === 401 ? logout : undefined}
              title="Question could not be answered"
            />
          ) : null}
        </form>

        <Separator className={styles.resultsDivider} />

        <div className={styles.answerStack}>
          {questionState === "loading" ? <LoadingAnswer /> : null}
          {questionState === "success" && answer ? (
            <>
              <AnswerPanel response={answer} />
              <CitationsPanel citations={answer.citations} />
              <div className={styles.answerActions}>
                <Button className={styles.resetButton} onClick={handleReset} type="button" variant="link">
                  <RotateCcw aria-hidden="true" />
                  Ask another question
                </Button>
                <Button asChild className={styles.historyLink} size="sm" type="button" variant="outline">
                  <Link href="/dashboard/history">View History</Link>
                </Button>
              </div>
            </>
          ) : null}
          {questionState === "idle" ? <EmptyAnswerState /> : null}
        </div>
      </div>
    </section>
  );
}
