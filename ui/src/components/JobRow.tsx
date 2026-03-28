import { useState } from 'react';
import type { Job } from '../types';
import { JobDetail } from './JobDetail';
import { resumeDownloadUrl } from '../api';

function scoreBadgeColor(score: number | null): string {
  if (score === null) return 'bg-[#1e293b] text-text-body';
  if (score >= 60) return 'bg-status-green/15 text-status-green';
  if (score >= 40) return 'bg-status-yellow/15 text-status-yellow';
  return 'bg-[#1e293b] text-text-body';
}

function locationBadge(loc: string, querySource: string | null) {
  const label = querySource === 'remote' ? 'Remote' : loc?.length > 20 ? loc.slice(0, 18) + '...' : loc;
  const color = querySource === 'remote' ? 'bg-accent-500/15 text-accent-500' : 'bg-[#1e293b] text-text-body';
  return <span className={`px-2 py-0.5 rounded text-xs ${color}`}>{label}</span>;
}

interface Props {
  job: Job;
  onPreviewResume: (dedupKey: string) => void;
}

export function JobRow({ job, onPreviewResume }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b border-border-subtle">
      <div
        className="grid grid-cols-[60px_1fr_160px_100px_180px] gap-3 items-center px-4 py-3 hover:bg-bg-surface/50 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Score */}
        <div className="flex justify-center">
          <span className={`inline-flex items-center justify-center w-10 h-10 rounded-lg text-sm font-semibold ${scoreBadgeColor(job.final_score)}`}>
            {job.final_score !== null ? Math.round(job.final_score) : '—'}
          </span>
        </div>

        {/* Title + Company */}
        <div className="min-w-0">
          <p className="text-text-heading text-sm font-medium truncate">
            {job.title_raw}
            {job.title_experimental && (
              <span className="ml-2 text-xs text-status-yellow">(experimental)</span>
            )}
          </p>
          <p className="text-xs text-text-body truncate">{job.company}</p>
        </div>

        {/* Location */}
        <div>{locationBadge(job.location, job.query_source)}</div>

        {/* Open Job */}
        <div>
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-500 hover:text-accent-600 hover:underline"
            onClick={e => e.stopPropagation()}
          >
            Open Job
          </a>
        </div>

        {/* Resume */}
        <div onClick={e => e.stopPropagation()}>
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
      </div>

      {expanded && <JobDetail job={job} />}
    </div>
  );
}
