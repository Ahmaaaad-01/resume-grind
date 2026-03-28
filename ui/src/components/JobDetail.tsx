import type { Job } from '../types';

function BarSegment({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="w-20 text-right text-text-body">{label}</span>
      <div className="flex-1 bg-[#1e293b] rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-text-heading font-medium">{value}</span>
    </div>
  );
}

export function JobDetail({ job }: { job: Job }) {
  const b = job.score_breakdown;

  return (
    <div className="px-4 pb-4 pt-1 bg-bg-surface/30">
      {b ? (
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-2">
            <p className="text-xs font-medium text-text-heading mb-2">Score Breakdown</p>
            <BarSegment label="Title" value={b.title} max={30} color="bg-accent-500" />
            <BarSegment label="YOE" value={b.yoe} max={20} color="bg-accent-500" />
            <BarSegment label="Location" value={b.location} max={10} color="bg-accent-500" />
            <BarSegment label="Company" value={b.company} max={10} color="bg-accent-500" />
            <BarSegment label="Recency" value={b.recency} max={5} color="bg-accent-500" />
            <BarSegment label="Keywords" value={b.keywords} max={25} color="bg-status-green" />
          </div>

          <div className="space-y-3">
            {b.keyword_matched_skills.length > 0 && (
              <div>
                <p className="text-xs font-medium text-text-heading mb-1">
                  Matched Keywords ({b.keyword_match_count})
                </p>
                <div className="flex flex-wrap gap-1">
                  {b.keyword_matched_skills.map(s => (
                    <span key={s} className="px-1.5 py-0.5 rounded text-[10px] bg-status-green/15 text-status-green">{s}</span>
                  ))}
                </div>
              </div>
            )}
            {b.keyword_missing_skills.length > 0 && (
              <div>
                <p className="text-xs font-medium text-text-heading mb-1">Missing Keywords</p>
                <div className="flex flex-wrap gap-1">
                  {b.keyword_missing_skills.map(s => (
                    <span key={s} className="px-1.5 py-0.5 rounded text-[10px] bg-status-red/15 text-status-red">{s}</span>
                  ))}
                </div>
              </div>
            )}

            <div className="text-xs text-text-body space-y-1 pt-1">
              {job.jd_source && <p>JD source: <span className="text-text-heading">{job.jd_source}</span></p>}
              {job.jd_word_count && <p>JD length: <span className="text-text-heading">{job.jd_word_count} words</span></p>}
              {job.times_seen > 1 && <p>Seen <span className="text-text-heading">{job.times_seen}x</span></p>}
            </div>
          </div>
        </div>
      ) : (
        <p className="text-xs text-text-body">Detailed score breakdown unavailable.</p>
      )}
    </div>
  );
}
