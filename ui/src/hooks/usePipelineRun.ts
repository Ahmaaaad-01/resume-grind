import { useState, useCallback, useRef } from 'react';
import type { PipelineEvent } from '../types';
import { subscribePipeline } from '../api';

const STAGES = ['discovery', 'filtering', 'scoring', 'tailoring', 'docx', 'done'];

export function usePipelineRun() {
  const [running, setRunning] = useState(false);
  const [currentStage, setCurrentStage] = useState('');
  const [message, setMessage] = useState('');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [lastData, setLastData] = useState<Record<string, unknown> | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);

  const start = useCallback((endpoint: string, body: unknown | null, onComplete?: () => void) => {
    setRunning(true);
    setError(null);
    setCurrentStage('');
    setMessage('Starting...');
    setProgress(0);
    setLastData(null);

    const cancel = subscribePipeline(
      endpoint,
      body,
      (event: PipelineEvent) => {
        setCurrentStage(event.stage);
        setMessage(event.message);
        setProgress(event.progress);
        if (event.data) setLastData(event.data);
        if (event.stage === 'error') setError(event.message);
      },
      () => {
        setRunning(false);
        onComplete?.();
      },
      (err) => {
        setError(err);
        setRunning(false);
      },
    );
    cancelRef.current = cancel;
  }, []);

  const cancel = useCallback(() => {
    cancelRef.current?.();
    setRunning(false);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { running, currentStage, message, progress, error, setError, clearError, lastData, start, cancel, stages: STAGES };
}
