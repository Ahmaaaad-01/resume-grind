import type { Job } from '../types';
import { JobRow } from './JobRow';

interface Props {
  jobs: Job[];
  dateGroups: string[];
  onPreviewResume: (dedupKey: string) => void;
}

export function JobList({ jobs, dateGroups, onPreviewResume }: Props) {
  if (jobs.length === 0) {
    return (
      <div className="text-center py-16 text-text-body">
        <p className="text-lg mb-2">No jobs found</p>
        <p className="text-sm">Run a SerpAPI query to discover new opportunities.</p>
      </div>
    );
  }

  const jobsByDate = new Map<string, Job[]>();
  for (const job of jobs) {
    const group = job.first_seen_run;
    if (!jobsByDate.has(group)) jobsByDate.set(group, []);
    jobsByDate.get(group)!.push(job);
  }

  return (
    <div>
      {/* Column headers */}
      <div className="grid grid-cols-[60px_1fr_160px_100px_180px] gap-3 items-center px-4 py-2 text-xs text-text-body font-medium uppercase tracking-wider border-b border-border-subtle">
        <span className="text-center">Score</span>
        <span>Title / Company</span>
        <span>Location</span>
        <span>Link</span>
        <span>Resume</span>
      </div>

      {dateGroups.map(dateStr => {
        const groupJobs = jobsByDate.get(dateStr) || [];
        if (groupJobs.length === 0) return null;
        return (
          <div key={dateStr}>
            <div className="px-4 py-2 bg-bg-primary sticky top-0 z-10">
              <span className="text-xs font-medium text-accent-500">{formatDate(dateStr)}</span>
              <span className="text-xs text-text-body ml-2">({groupJobs.length} jobs)</span>
            </div>
            {groupJobs.map(job => (
              <JobRow key={job.dedup_key} job={job} onPreviewResume={onPreviewResume} />
            ))}
          </div>
        );
      })}
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return iso;
  }
}
