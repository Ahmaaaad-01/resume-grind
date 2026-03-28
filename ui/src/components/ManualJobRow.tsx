import type { ManualJob } from '../types';
import { resumeDownloadUrl } from '../api';

interface Props {
  job: ManualJob;
  onPreviewResume: (dedupKey: string) => void;
  onDelete: (job: ManualJob) => void;
  onRegenerate: (dedupKey: string) => void;
  regenerating: string | null;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

export function ManualJobRow({ job, onPreviewResume, onDelete, onRegenerate, regenerating }: Props) {
  const isRegenerating = regenerating === job.dedup_key;

  return (
    <div className="border-b border-border-subtle">
      <div className="grid grid-cols-[1fr_140px_180px_200px] gap-3 items-center px-4 py-3">
        {/* Title + Company */}
        <div className="min-w-0">
          <p className="text-text-heading text-sm font-medium truncate">{job.title_raw}</p>
          <p className="text-xs text-text-body truncate">{job.company}</p>
        </div>

        {/* Date submitted */}
        <div>
          <span className="text-xs text-text-body">{formatDate(job.created_at)}</span>
        </div>

        {/* Resume actions */}
        <div>
          {job.resume_status === 'available' ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => onPreviewResume(job.dedup_key)}
                className="px-2.5 py-1 text-xs rounded bg-accent-500/15 text-accent-500 hover:bg-accent-500/25 transition-colors"
              >
                Preview
              </button>
              <a
                href={resumeDownloadUrl(job.dedup_key)}
                className="px-2.5 py-1 text-xs rounded bg-[#1e293b] text-text-body hover:text-text-heading transition-colors"
              >
                Download
              </a>
            </div>
          ) : (
            <span className="text-xs text-text-body">{job.resume_status_label}</span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-accent-500 hover:text-accent-600 hover:underline"
            >
              Open Job
            </a>
          )}
          <button
            onClick={() => onRegenerate(job.dedup_key)}
            disabled={isRegenerating}
            className="px-2 py-1 text-xs rounded bg-[#1e293b] text-text-body hover:text-text-heading disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isRegenerating ? 'Regenerating...' : 'Re-generate'}
          </button>
          <button
            onClick={() => onDelete(job)}
            disabled={isRegenerating}
            className="px-2 py-1 text-xs rounded text-status-red hover:bg-status-red/15 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
