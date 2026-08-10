"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type RequestState<T> =
  | { status: "loading"; data?: undefined; error?: undefined }
  | {
      status: "success";
      data: T;
      error?: undefined;
      isRefreshing: boolean;
      refreshError?: unknown;
    }
  | { status: "error"; data?: undefined; error: unknown };

export function useApiRequest<T>(request: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<RequestState<T>>({ status: "loading" });
  const dataRef = useRef<T | undefined>(undefined);
  const controllerRef = useRef<AbortController | null>(null);
  const requestSequence = useRef(0);

  const execute = useCallback(async (options: { silent?: boolean } = {}) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const sequence = ++requestSequence.current;
    const retainedData = dataRef.current;
    if (options.silent && retainedData !== undefined) {
      setState({
        status: "success",
        data: retainedData,
        isRefreshing: true,
      });
    } else {
      setState({ status: "loading" });
    }

    try {
      const data = await request(controller.signal);
      if (!controller.signal.aborted && sequence === requestSequence.current) {
        dataRef.current = data;
        setState({ status: "success", data, isRefreshing: false });
      }
      return data;
    } catch (error) {
      if (!controller.signal.aborted && sequence === requestSequence.current) {
        if (options.silent && retainedData !== undefined) {
          setState({
            status: "success",
            data: retainedData,
            isRefreshing: false,
            refreshError: error,
          });
        } else {
          setState({ status: "error", error });
        }
      }
      throw error;
    }
  }, [request]);

  useEffect(() => {
    void execute().catch(() => undefined);
    return () => controllerRef.current?.abort();
  }, [execute]);

  return { ...state, refetch: execute };
}

export function useApiMutation<TInput, TOutput>(
  mutation: (input: TInput, signal: AbortSignal) => Promise<TOutput>,
) {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const controllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const pendingRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      controllerRef.current?.abort();
    };
  }, []);

  const reset = useCallback(() => setError(undefined), []);

  const mutate = useCallback(
    async (input: TInput) => {
      if (pendingRef.current) {
        throw new Error("A request is already in progress.");
      }

      const controller = new AbortController();
      controllerRef.current = controller;
      pendingRef.current = true;
      setIsPending(true);
      setError(undefined);

      try {
        return await mutation(input, controller.signal);
      } catch (nextError) {
        if (!controller.signal.aborted && mountedRef.current) {
          setError(nextError);
        }
        throw nextError;
      } finally {
        pendingRef.current = false;
        if (!controller.signal.aborted && mountedRef.current) {
          setIsPending(false);
        }
      }
    },
    [mutation],
  );

  return { error, isPending, mutate, reset };
}
