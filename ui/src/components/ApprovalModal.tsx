import { useState } from 'react';
import type { EligibleJob } from '../types';

interface Props {
  jobs: EligibleJob[];
  threshold: number;
  onApprove: (selectedKeys: string[]) => void;
  onCancel: () => void;
}

export function ApprovalModal({ jobs, threshold, onApprove, onCancel }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set(jobs.map(j => j.dedup_key)));

  const toggle = (key: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === jobs.length) setSelected(new Set());
    else setSelected(new Set(jobs.map(j => j.dedup_key)));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-bg-surface border border-border-subtle rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="px-6 py-4 border-b border-border-subtle">
          <h2 className="text-lg font-semibold text-text-heading">Select Jobs for Resume Generation</h2>
          <p className="text-xs text-text-body mt-1">
            {jobs.length} eligible jobs (score &ge; {threshold}). Uncheck any you want to skip.
          </p>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-3">
          <div className="flex items-center gap-2 mb-3">
            <input
              type="checkbox"
              checked={selected.size === jobs.length}
              onChange={toggleAll}
              className="accent-accent-500"
            />
            <span className="text-xs text-text-body">
              {selected.size === jobs.length ? 'Deselect all' : 'Select all'}
            </span>
          </div>

          <div className="space-y-1">
            {jobs.map(job => (
              <label
                key={job.dedup_key}
                className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-bg-primary/50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selected.has(job.dedup_key)}
                  onChange={() => toggle(job.dedup_key)}
                  className="accent-accent-500"
                />
                <span className="text-sm text-text-heading flex-1 truncate">
                  {job.title_raw} <span className="text-text-body">at</span> {job.company}
                </span>
                <span className="text-xs text-text-body">{job.location}</span>
                <span className="text-xs font-medium text-status-green">
                  {job.final_score !== null ? Math.round(job.final_score) : '—'}
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="px-6 py-4 border-t border-border-subtle flex items-center justify-between">
          <p className="text-xs text-text-body">
            {selected.size} selected &middot; ~{selected.size} API call{selected.size !== 1 ? 's' : ''}
          </p>
          <div className="flex gap-3">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm rounded-lg text-text-body hover:text-text-heading transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => onApprove([...selected])}
              disabled={selected.size === 0}
              className="px-4 py-2 text-sm rounded-lg bg-accent-500 text-bg-primary font-medium hover:bg-accent-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Approve &amp; Generate ({selected.size})
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
