"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useApiMutation } from "@/hooks/use-api-request";
import { askQuestionApi } from "../questions-api";
import type {
  AskQuestionApiInput,
  QuestionAnswer,
} from "../questions-api-types";

export type AskQuestionSubmission = AskQuestionApiInput & {
  scopeLabel: string;
};

export type AskQuestionState =
  | { status: "idle" }
  | { status: "submitting"; submission: AskQuestionSubmission }
  | {
      status: "completed";
      answer: QuestionAnswer;
      submission: AskQuestionSubmission;
    }
  | {
      status: "failed";
      error: unknown;
      submission: AskQuestionSubmission;
    };

export function useAskQuestion() {
  const [state, setState] = useState<AskQuestionState>({ status: "idle" });
  const {
    mutate,
    reset: resetMutation,
  } = useApiMutation(
    (input: AskQuestionApiInput, signal: AbortSignal) =>
      askQuestionApi(input, signal),
  );
  const sequenceRef = useRef(0);
  const mountedRef = useRef(true);
  const pendingRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      sequenceRef.current += 1;
    };
  }, []);

  const submit = useCallback(
    async (submission: AskQuestionSubmission) => {
      if (pendingRef.current) return;

      pendingRef.current = true;
      const sequence = ++sequenceRef.current;
      setState({ status: "submitting", submission });

      try {
        const answer = await mutate({
          collectionId: submission.collectionId,
          question: submission.question,
        });
        if (mountedRef.current && sequence === sequenceRef.current) {
          setState({ answer, status: "completed", submission });
        }
      } catch (error) {
        if (mountedRef.current && sequence === sequenceRef.current) {
          setState({ error, status: "failed", submission });
        }
        throw error;
      } finally {
        pendingRef.current = false;
      }
    },
    [mutate],
  );

  const reset = useCallback(() => {
    sequenceRef.current += 1;
    resetMutation();
    setState({ status: "idle" });
  }, [resetMutation]);

  const dismissFailure = useCallback(() => {
    resetMutation();
    setState((current) =>
      current.status === "failed" ? { status: "idle" } : current,
    );
  }, [resetMutation]);

  return {
    dismissFailure,
    isPending: state.status === "submitting",
    reset,
    state,
    submit,
  };
}
