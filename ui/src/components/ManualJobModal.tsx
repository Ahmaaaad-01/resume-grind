import { useState } from 'react';
import type { ManualJobRequest } from '../types';

interface Props {
  onSubmit: (request: ManualJobRequest) => Promise<void>;
  onClose: () => void;
}

export function ManualJobModal({ onSubmit, onClose }: Props) {
  const [jdText, setJdText] = useState('');
  const [company, setCompany] = useState('');
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wordCount = jdText.trim().split(/\s+/).filter(Boolean).length;
  const isValid = wordCount >= 50;

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        jd_text: jdText.trim(),
        company: company.trim() || undefined,
        title: title.trim() || undefined,
        url: url.trim() || undefined,
      });
    } catch (err) {
      setError(String(err));
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-bg-surface border border-border-subtle rounded-xl shadow-xl w-full max-w-lg mx-4"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
          <h2 className="text-sm font-semibold text-text-heading">Submit Job for Resume Generation</h2>
          <button
            onClick={onClose}
            className="text-text-body hover:text-text-heading text-lg leading-none"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-4">
          {/* JD Text */}
          <div>
            <label className="block text-xs font-medium text-text-heading mb-1">
              Job Description <span className="text-status-red">*</span>
            </label>
            <textarea
              value={jdText}
              onChange={e => setJdText(e.target.value)}
              disabled={submitting}
              rows={10}
              placeholder="Paste the full job description here..."
              className="w-full px-3 py-2 text-sm bg-bg-primary border border-border-subtle rounded-lg text-text-heading placeholder-text-body/40 focus:outline-none focus:border-accent-500 disabled:opacity-50 resize-y"
            />
            <p className={`text-xs mt-1 ${wordCount >= 50 ? 'text-text-body' : 'text-status-amber'}`}>
              {wordCount} word{wordCount !== 1 ? 's' : ''}{wordCount < 50 ? ' — minimum 50 required' : ''}
            </p>
          </div>

          {/* Company */}
          <div>
            <label className="block text-xs font-medium text-text-heading mb-1">Company (optional)</label>
            <input
              type="text"
              value={company}
              onChange={e => setCompany(e.target.value)}
              disabled={submitting}
              placeholder="Leave blank to auto-detect from JD"
              className="w-full px-3 py-1.5 text-sm bg-bg-primary border border-border-subtle rounded-lg text-text-heading placeholder-text-body/40 focus:outline-none focus:border-accent-500 disabled:opacity-50"
            />
          </div>

          {/* Title */}
          <div>
            <label className="block text-xs font-medium text-text-heading mb-1">Job Title (optional)</label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              disabled={submitting}
              placeholder="Leave blank to auto-detect from JD"
              className="w-full px-3 py-1.5 text-sm bg-bg-primary border border-border-subtle rounded-lg text-text-heading placeholder-text-body/40 focus:outline-none focus:border-accent-500 disabled:opacity-50"
            />
          </div>

          {/* URL */}
          <div>
            <label className="block text-xs font-medium text-text-heading mb-1">Job URL (optional)</label>
            <input
              type="text"
              value={url}
              onChange={e => setUrl(e.target.value)}
              disabled={submitting}
              placeholder='For "Open Job" link only'
              className="w-full px-3 py-1.5 text-sm bg-bg-primary border border-border-subtle rounded-lg text-text-heading placeholder-text-body/40 focus:outline-none focus:border-accent-500 disabled:opacity-50"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="px-3 py-2 rounded-lg bg-status-red/15 border border-status-red/30 text-xs text-status-red">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-border-subtle">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-1.5 text-xs rounded-lg text-text-body hover:text-text-heading transition-colors disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!isValid || submitting}
            className="px-4 py-1.5 text-xs rounded-lg bg-accent-500 text-bg-primary font-medium hover:bg-accent-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {submitting && (
              <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {submitting ? 'Generating...' : 'Generate Resume'}
          </button>
        </div>
      </div>
    </div>
  );
}
