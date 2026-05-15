import { startTransition, useEffect, useEffectEvent, useState } from 'react';
import { toast } from 'sonner';
import { getErrorDetail } from '@/api/client';
import type { ApiFeature, ApiProductProposal } from '@/api/types';
import { POLL_INTERVAL_MS } from '../constants';
import type { LoadOrigin } from '../types';
import { loadProductResearchSnapshot } from '../utils';

export type ProductResearchSnapshotState = {
  proposals: ApiProductProposal[];
  features: ApiFeature[];
  isLoading: boolean;
  loadError: string | null;
  reloadSnapshot: (origin: LoadOrigin) => Promise<void>;
};

export function useProductResearchSnapshot(): ProductResearchSnapshotState {
  const [proposals, setProposals] = useState<ApiProductProposal[]>([]);
  const [features, setFeatures] = useState<ApiFeature[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  async function reloadSnapshot(origin: LoadOrigin): Promise<void> {
    try {
      const snapshot = await loadProductResearchSnapshot();
      startTransition(() => {
        setProposals(snapshot.proposals);
        setFeatures(snapshot.features);
        setLoadError(null);
        setIsLoading(false);
      });
    } catch (error) {
      const detail = getErrorDetail(error, 'Failed to load product research data.');
      startTransition(() => {
        setLoadError(detail);
        setIsLoading(false);
      });
      if (origin !== 'poll') {
        toast.error('Failed to load product research', {
          description: detail,
        });
      }
    }
  }

  const pollLatest = useEffectEvent(async () => {
    await reloadSnapshot('poll');
  });

  useEffect(() => {
    void reloadSnapshot('initial');

    const intervalId = window.setInterval(() => {
      void pollLatest();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, []);

  return {
    proposals,
    features,
    isLoading,
    loadError,
    reloadSnapshot,
  };
}
