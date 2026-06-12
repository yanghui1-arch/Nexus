import { startTransition, useCallback, useEffect, useRef, useState } from 'react';
import { getErrorDetail } from '@/api/client';
import { getTaskObservability } from '@/api/observability';
import type { ApiTaskExecutionEvent, ApiTaskObservabilityMetrics } from '@/api/types';

type TaskObservabilityData = {
  events: ApiTaskExecutionEvent[];
  metrics: ApiTaskObservabilityMetrics | null;
};

export type UseTaskObservabilityResult = TaskObservabilityData & {
  error: string | null;
  isLoading: boolean;
  isRefreshing: boolean;
  refresh: () => Promise<void>;
};

const EMPTY_DATA: TaskObservabilityData = { events: [], metrics: null };

export function useTaskObservability(taskId: string | null | undefined): UseTaskObservabilityResult {
  const [data, setData] = useState<TaskObservabilityData>(EMPTY_DATA);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(taskId));
  const [isRefreshing, setIsRefreshing] = useState(false);
  const requestIdRef = useRef(0);
  const dataRef = useRef(data);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  const refresh = useCallback(async () => {
    const selectedTaskId = taskId;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    if (!selectedTaskId) {
      startTransition(() => {
        setData(EMPTY_DATA);
        setError(null);
        setIsLoading(false);
        setIsRefreshing(false);
      });
      return;
    }

    const hasLoadedData = dataRef.current.metrics !== null;
    startTransition(() => {
      setError(null);
      setIsLoading(!hasLoadedData);
      setIsRefreshing(hasLoadedData);
    });

    try {
      const nextData = await getTaskObservability(selectedTaskId);
      if (requestIdRef.current !== requestId) return;
      startTransition(() => {
        setData(nextData);
        setError(null);
        setIsLoading(false);
        setIsRefreshing(false);
      });
    } catch (caughtError) {
      if (requestIdRef.current !== requestId) return;
      startTransition(() => {
        setError(getErrorDetail(caughtError, 'Failed to load observability data.'));
        setIsLoading(false);
        setIsRefreshing(false);
      });
    }
  }, [taskId]);

  useEffect(() => {
    requestIdRef.current += 1;
    dataRef.current = EMPTY_DATA;
    startTransition(() => {
      setData(EMPTY_DATA);
      setError(null);
      setIsLoading(Boolean(taskId));
      setIsRefreshing(false);
    });
  }, [taskId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { ...data, error, isLoading, isRefreshing, refresh };
}
