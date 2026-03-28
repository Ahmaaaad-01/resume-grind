import type { ManualJob } from '../types';
import { ManualJobRow } from './ManualJobRow';

interface Props {
  jobs: ManualJob[];
  onPreviewResume: (dedupKey: string) => void;
  onDelete: (job: ManualJob) => void;
  onRegenerate: (dedupKey: string) => void;
  regenerating: string | null;
}

export function ManualJobList({ jobs, onPreviewResume, onDelete, onRegenerate, regenerating }: Props) {
  if (jobs.length === 0) {
    return (
      <div className="text-center py-16 text-text-body">
        <p className="text-sm">No manual jobs yet.</p>
        <p className="text-xs mt-1 opacity-60">Click "+ Submit Job" to generate a tailored resume from any job description.</p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="grid grid-cols-[1fr_140px_180px_200px] gap-3 px-4 py-2 border-b border-border-subtle text-xs text-text-body font-medium uppercase tracking-wider">
        <span>Title / Company</span>
        <span>Date Submitted</span>
        <span>Resume</span>
        <span>Actions</span>
      </div>

      {/* Rows */}
      {jobs.map(job => (
        <ManualJobRow
          key={job.dedup_key}
          job={job}
          onPreviewResume={onPreviewResume}
          onDelete={onDelete}
          onRegenerate={onRegenerate}
          regenerating={regenerating}
        />
      ))}
    </div>
  );
}
