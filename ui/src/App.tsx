import { useState, useCallback, useEffect } from 'react';
import { useAuth } from './context/AuthContext';
import { useJobs } from './hooks/useJobs';
import { useManualJobs } from './hooks/useManualJobs';
import { usePipelineRun } from './hooks/usePipelineRun';
import { fetchEligibleJobs, submitManualJob, deleteManualJob, regenerateManualJob } from './api';
import { JobList } from './components/JobList';
import { ManualJobList } from './components/ManualJobList';
import { ActionBar } from './components/ActionBar';
import { ProgressBar } from './components/ProgressBar';
import { ApprovalModal } from './components/ApprovalModal';
import { ResumePreview } from './components/ResumePreview';
import { ManualJobModal } from './components/ManualJobModal';
import { DeleteConfirmModal } from './components/DeleteConfirmModal';
import { LoginPage } from './pages/LoginPage';
import { SettingsPage } from './pages/SettingsPage';
import type { EligibleJob, ManualJob, ManualJobRequest } from './types';

type Tab = 'discovered' | 'manual' | 'settings';

function Dashboard() {
  const { user, logout } = useAuth();
  const { jobs, dateGroups, total, loading, error, showAll, setShowAll, refresh } = useJobs();
  const manual = useManualJobs();
  const pipeline = usePipelineRun();

  // Tab state
  const [activeTab, setActiveTab] = useState<Tab>('discovered');

  // Approval modal state
  const [approvalJobs, setApprovalJobs] = useState<EligibleJob[] | null>(null);
  const [approvalThreshold, setApprovalThreshold] = useState(60);

  // Resume preview state
  const [previewKey, setPreviewKey] = useState<string | null>(null);

  // Manual job modal state
  const [showSubmitModal, setShowSubmitModal] = useState(false);

  // Delete confirm state
  const [deleteTarget, setDeleteTarget] = useState<ManualJob | null>(null);

  // Regenerate spinner
  const [regenerating, setRegenerating] = useState<string | null>(null);

  // Success toast
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Auto-dismiss error and success toasts
  useEffect(() => {
    if (pipeline.error) {
      const t = setTimeout(() => pipeline.clearError(), 8000);
      return () => clearTimeout(t);
    }
  }, [pipeline.error, pipeline.clearError]);

  useEffect(() => {
    if (successMsg) {
      const t = setTimeout(() => setSuccessMsg(null), 5000);
      return () => clearTimeout(t);
    }
  }, [successMsg]);

  // -- Pipeline handlers --

  const handleRunDiscovery = useCallback(() => {
    pipeline.start('/api/run/discovery', null, () => {
      refresh();
      setSuccessMsg('Discovery complete — jobs list updated.');
    });
  }, [pipeline, refresh]);

  const handleRunBoth = useCallback(() => {
    pipeline.start('/api/run/discovery', null, async () => {
      try {
        const data = await fetchEligibleJobs();
        if (data.jobs.length > 0) {
          setApprovalJobs(data.jobs);
          setApprovalThreshold(data.threshold);
        } else {
          refresh();
          setSuccessMsg('Discovery complete — no eligible jobs for resume generation.');
        }
      } catch {
        refresh();
      }
    });
  }, [pipeline, refresh]);

  const handleRunResumes = useCallback(async () => {
    try {
      const data = await fetchEligibleJobs();
      if (data.jobs.length === 0) {
        setSuccessMsg('No eligible jobs found for resume generation.');
        return;
      }
      setApprovalJobs(data.jobs);
      setApprovalThreshold(data.threshold);
    } catch (err) {
      pipeline.setError(`Failed to fetch eligible jobs: ${err}`);
    }
  }, [pipeline]);

  const handleApprove = useCallback((selectedKeys: string[]) => {
    setApprovalJobs(null);
    pipeline.start('/api/run/generate-resumes', { dedup_keys: selectedKeys }, () => {
      refresh();
      setSuccessMsg(`Resume generation complete — ${selectedKeys.length} job(s) processed.`);
    });
  }, [pipeline, refresh]);

  const handleCancelApproval = useCallback(() => {
    setApprovalJobs(null);
    refresh();
  }, [refresh]);

  // -- Manual job handlers --

  const handleSubmitJob = useCallback(async (request: ManualJobRequest) => {
    await submitManualJob(request);
    setShowSubmitModal(false);
    manual.refresh();
    setActiveTab('manual');
    setSuccessMsg(`Resume generated for ${request.company || 'submitted job'}.`);
  }, [manual]);

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      await deleteManualJob(deleteTarget.dedup_key);
      setDeleteTarget(null);
      manual.refresh();
      setSuccessMsg(`Deleted ${deleteTarget.title_raw} at ${deleteTarget.company}.`);
    } catch (err) {
      setSuccessMsg(null);
      pipeline.setError(`Delete failed: ${err}`);
      setDeleteTarget(null);
    }
  }, [deleteTarget, manual, pipeline]);

  const handleRegenerate = useCallback(async (dedupKey: string) => {
    setRegenerating(dedupKey);
    try {
      await regenerateManualJob(dedupKey);
      manual.refresh();
      setSuccessMsg('Resume re-generated successfully.');
    } catch (err) {
      pipeline.setError(`Regenerate failed: ${err}`);
    } finally {
      setRegenerating(null);
    }
  }, [manual, pipeline]);

  return (
    <div className="min-h-screen bg-bg-primary">
      {/* Header */}
      <header className="border-b border-border-subtle bg-bg-surface/50 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-semibold text-text-heading tracking-tight">PM Job Pipeline</h1>
            <span className="text-xs text-text-body">{total} jobs</span>
          </div>
          <div className="flex items-center gap-4">
            <ActionBar
              onRunBoth={handleRunBoth}
              onRunDiscovery={handleRunDiscovery}
              onRunResumes={handleRunResumes}
              onSubmitJob={() => setShowSubmitModal(true)}
              running={pipeline.running}
            />
            {user && (
              <div className="flex items-center gap-2 ml-4 border-l border-border-subtle pl-4">
                {user.picture && (
                  <img src={user.picture} alt="" className="w-6 h-6 rounded-full" />
                )}
                <span className="text-xs text-text-body">{user.name || user.email}</span>
                <button
                  onClick={logout}
                  className="text-xs text-text-body hover:text-status-red transition-colors"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-4">
        {/* Progress bar */}
        {pipeline.running && (
          <ProgressBar
            currentStage={pipeline.currentStage}
            message={pipeline.message}
            progress={pipeline.progress}
            stages={pipeline.stages}
          />
        )}

        {/* Success toast */}
        {successMsg && (
          <div
            className="mb-4 px-4 py-3 rounded-lg bg-status-green/15 border border-status-green/30 text-sm text-status-green flex items-center justify-between cursor-pointer"
            onClick={() => setSuccessMsg(null)}
          >
            <span>{successMsg}</span>
            <span className="text-xs opacity-60">dismiss</span>
          </div>
        )}

        {/* Error toast */}
        {pipeline.error && (
          <div
            className="mb-4 px-4 py-3 rounded-lg bg-status-red/15 border border-status-red/30 text-sm text-status-red flex items-center justify-between cursor-pointer"
            onClick={() => pipeline.clearError()}
          >
            <span>{pipeline.error}</span>
            <span className="text-xs opacity-60">dismiss</span>
          </div>
        )}

        {/* Tab navigation */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveTab('discovered')}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                activeTab === 'discovered'
                  ? 'bg-accent-500/15 text-accent-500 font-medium'
                  : 'text-text-body hover:text-text-heading'
              }`}
            >
              Discovered Jobs
            </button>
            <button
              onClick={() => setActiveTab('manual')}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                activeTab === 'manual'
                  ? 'bg-accent-500/15 text-accent-500 font-medium'
                  : 'text-text-body hover:text-text-heading'
              }`}
            >
              Manual Jobs{manual.total > 0 ? ` (${manual.total})` : ''}
            </button>
            <button
              onClick={() => setActiveTab('settings')}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                activeTab === 'settings'
                  ? 'bg-accent-500/15 text-accent-500 font-medium'
                  : 'text-text-body hover:text-text-heading'
              }`}
            >
              Settings
            </button>
          </div>

          {/* View toggle — only for Discovered tab */}
          {activeTab === 'discovered' && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowAll(false)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                  !showAll ? 'bg-accent-500/15 text-accent-500' : 'text-text-body hover:text-text-heading'
                }`}
              >
                Last 7 Days
              </button>
              <button
                onClick={() => setShowAll(true)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                  showAll ? 'bg-accent-500/15 text-accent-500' : 'text-text-body hover:text-text-heading'
                }`}
              >
                All Jobs
              </button>
              <button
                onClick={refresh}
                disabled={loading}
                className="text-xs text-text-body hover:text-text-heading transition-colors ml-2"
              >
                Refresh
              </button>
            </div>
          )}

          {activeTab === 'manual' && (
            <button
              onClick={manual.refresh}
              disabled={manual.loading}
              className="text-xs text-text-body hover:text-text-heading transition-colors"
            >
              Refresh
            </button>
          )}
        </div>

        {/* Discovered Jobs tab */}
        {activeTab === 'discovered' && (
          <>
            {loading && (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-14 bg-bg-surface/50 rounded-lg animate-pulse" />
                ))}
              </div>
            )}

            {error && !loading && (
              <div className="text-center py-16 text-status-red">
                <p>Failed to load jobs: {error}</p>
                <button onClick={refresh} className="mt-2 text-accent-500 text-sm underline">Retry</button>
              </div>
            )}

            {!loading && !error && (
              <div className="bg-bg-surface border border-border-subtle rounded-xl overflow-hidden">
                <JobList jobs={jobs} dateGroups={dateGroups} onPreviewResume={setPreviewKey} />
              </div>
            )}
          </>
        )}

        {/* Manual Jobs tab */}
        {activeTab === 'manual' && (
          <>
            {manual.loading && (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="h-14 bg-bg-surface/50 rounded-lg animate-pulse" />
                ))}
              </div>
            )}

            {manual.error && !manual.loading && (
              <div className="text-center py-16 text-status-red">
                <p>Failed to load manual jobs: {manual.error}</p>
                <button onClick={manual.refresh} className="mt-2 text-accent-500 text-sm underline">Retry</button>
              </div>
            )}

            {!manual.loading && !manual.error && (
              <div className="bg-bg-surface border border-border-subtle rounded-xl overflow-hidden">
                <ManualJobList
                  jobs={manual.jobs}
                  onPreviewResume={setPreviewKey}
                  onDelete={setDeleteTarget}
                  onRegenerate={handleRegenerate}
                  regenerating={regenerating}
                />
              </div>
            )}
          </>
        )}

        {/* Settings tab */}
        {activeTab === 'settings' && <SettingsPage />}
      </main>

      {/* Approval modal */}
      {approvalJobs && (
        <ApprovalModal
          jobs={approvalJobs}
          threshold={approvalThreshold}
          onApprove={handleApprove}
          onCancel={handleCancelApproval}
        />
      )}

      {/* Resume preview */}
      {previewKey && (
        <ResumePreview dedupKey={previewKey} onClose={() => setPreviewKey(null)} />
      )}

      {/* Manual job submission modal */}
      {showSubmitModal && (
        <ManualJobModal
          onSubmit={handleSubmitJob}
          onClose={() => setShowSubmitModal(false)}
        />
      )}

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <DeleteConfirmModal
          job={deleteTarget}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

export default function App() {
  const { user, loading, googleClientId } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center">
        <div className="text-text-body text-sm">Loading...</div>
      </div>
    );
  }

  // If Google OAuth is configured and user is not logged in, show login
  if (googleClientId && !user) {
    return <LoginPage />;
  }

  // Otherwise show the dashboard (works in local mode without auth too)
  return <Dashboard />;
}
