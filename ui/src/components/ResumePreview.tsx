import { resumePreviewUrl, resumeDownloadUrl } from '../api';

interface Props {
  dedupKey: string;
  onClose: () => void;
}

export function ResumePreview({ dedupKey, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-bg-surface border border-border-subtle rounded-xl w-full max-w-4xl h-[85vh] flex flex-col">
        <div className="px-6 py-3 border-b border-border-subtle flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-heading">Resume Preview</h2>
          <div className="flex items-center gap-3">
            <a
              href={resumeDownloadUrl(dedupKey)}
              className="px-3 py-1.5 text-xs rounded-lg bg-accent-500/15 text-accent-500 hover:bg-accent-500/25 transition-colors"
            >
              Download DOCX
            </a>
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs rounded-lg text-text-body hover:text-text-heading transition-colors"
            >
              Close
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <iframe
            src={resumePreviewUrl(dedupKey)}
            className="w-full h-full border-0 bg-white"
            title="Resume Preview"
          />
        </div>
      </div>
    </div>
  );
}
