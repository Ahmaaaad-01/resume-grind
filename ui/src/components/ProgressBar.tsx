const STAGE_LABELS: Record<string, string> = {
  discovery: 'Discovery',
  filtering: 'Filtering',
  scoring: 'Scoring',
  tailoring: 'Tailoring',
  docx: 'Generating',
  done: 'Done',
  error: 'Error',
};

interface Props {
  currentStage: string;
  message: string;
  progress: number;
  stages: string[];
}

export function ProgressBar({ currentStage, message, progress, stages }: Props) {
  const currentIdx = stages.indexOf(currentStage);

  return (
    <div className="bg-bg-surface border border-border-subtle rounded-lg p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        {stages.filter(s => s !== 'done').map((stage, i) => {
          let color = 'bg-[#1e293b] text-text-body';
          if (i < currentIdx || currentStage === 'done') color = 'bg-status-green/20 text-status-green';
          else if (i === currentIdx) color = 'bg-accent-500/20 text-accent-500';
          return (
            <div key={stage} className="flex items-center gap-2">
              {i > 0 && <div className={`w-6 h-px ${i <= currentIdx ? 'bg-status-green/40' : 'bg-[#1e293b]'}`} />}
              <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${color}`}>
                {STAGE_LABELS[stage] || stage}
              </span>
            </div>
          );
        })}
      </div>
      <div className="w-full bg-[#1e293b] rounded-full h-1.5 mb-2">
        <div
          className="bg-accent-500 h-1.5 rounded-full transition-all duration-300"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>
      <p className="text-xs text-text-body">{message}</p>
    </div>
  );
}
