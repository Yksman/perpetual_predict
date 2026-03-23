import { useState, useEffect } from 'react';
import { DATA_BASE_URL } from '../constants';
import type { PredictionsData, TradesData, MetricsData, MetaData } from '../types';

interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function useFetch<T>(filename: string): FetchState<T> {
  const [state, setState] = useState<FetchState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        const url = `${DATA_BASE_URL}/${filename}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Failed to fetch ${filename}: ${res.status}`);
        const data = await res.json();
        if (!cancelled) setState({ data, loading: false, error: null });
      } catch (err) {
        if (!cancelled) {
          setState({ data: null, loading: false, error: (err as Error).message });
        }
      }
    }

    fetchData();
    return () => { cancelled = true; };
  }, [filename]);

  return state;
}

export function usePredictions() {
  return useFetch<PredictionsData>('predictions.json');
}

export function useTrades() {
  return useFetch<TradesData>('trades.json');
}

export function useMetrics() {
  return useFetch<MetricsData>('metrics.json');
}

export function useMeta() {
  return useFetch<MetaData>('meta.json');
}
