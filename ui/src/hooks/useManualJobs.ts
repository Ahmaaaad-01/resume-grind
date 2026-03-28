import { useState, useEffect, useCallback } from 'react';
import type { ManualJob } from '../types';
import { fetchManualJobs } from '../api';

export function useManualJobs() {
  const [jobs, setJobs] = useState<ManualJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchManualJobs();
      setJobs(data.jobs);
      setTotal(data.total);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return { jobs, total, loading, error, refresh: load };
}
