interface Props {
  onRunBoth: () => void;
  onRunDiscovery: () => void;
  onRunResumes: () => void;
  onSubmitJob: () => void;
  running: boolean;
}

export function ActionBar({ onRunBoth, onRunDiscovery, onRunResumes, onSubmitJob, running }: Props) {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onSubmitJob}
        disabled={running}
        className="px-3 py-1.5 text-xs rounded-lg bg-status-green/15 border border-status-green/30 text-status-green font-medium hover:bg-status-green/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        + Submit Job
      </button>
      <div className="w-px h-5 bg-border-subtle mx-1" />
      <button
        onClick={onRunBoth}
        disabled={running}
        className="px-3 py-1.5 text-xs rounded-lg bg-accent-500 text-bg-primary font-medium hover:bg-accent-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        SerpAPI + Resume
      </button>
      <button
        onClick={onRunDiscovery}
        disabled={running}
        className="px-3 py-1.5 text-xs rounded-lg bg-bg-surface border border-border-subtle text-text-heading hover:bg-[#1e293b] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        SerpAPI Only
      </button>
      <button
        onClick={onRunResumes}
        disabled={running}
        className="px-3 py-1.5 text-xs rounded-lg bg-bg-surface border border-border-subtle text-text-heading hover:bg-[#1e293b] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Resume Builder
      </button>
    </div>
  );
}
