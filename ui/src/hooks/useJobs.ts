import { useState, useEffect, useCallback } from 'react';
import type { Job, JobListResponse } from '../types';
import { fetchJobs } from '../api';

export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [dateGroups, setDateGroups] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: JobListResponse = await fetchJobs(showAll ? 30 : days, showAll);
      setJobs(data.jobs);
      setDateGroups(data.date_groups);
      setTotal(data.total);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [days, showAll]);

  useEffect(() => { load(); }, [load]);

  return { jobs, dateGroups, total, loading, error, days, setDays, showAll, setShowAll, refresh: load };
}
