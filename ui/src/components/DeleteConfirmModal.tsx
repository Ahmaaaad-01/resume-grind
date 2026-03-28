import type { ManualJob } from '../types';

interface Props {
  job: ManualJob;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteConfirmModal({ job, onConfirm, onCancel }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onCancel}>
      <div
        className="bg-bg-surface border border-border-subtle rounded-xl shadow-xl w-full max-w-sm mx-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="px-5 py-4">
          <h2 className="text-sm font-semibold text-text-heading mb-2">Delete Manual Job?</h2>
          <p className="text-xs text-text-body mb-3">
            This will permanently delete the job record and its generated resume file.
          </p>
          <p className="text-xs text-text-heading font-medium">
            {job.title_raw} at {job.company}
          </p>
        </div>
        <div className="flex items-center justify-end gap-3 px-5 py-3 border-t border-border-subtle">
          <button
            onClick={onCancel}
            className="px-4 py-1.5 text-xs rounded-lg text-text-body hover:text-text-heading transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-1.5 text-xs rounded-lg bg-status-red text-white font-medium hover:bg-status-red/80 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
