import { useState, useEffect, useRef } from 'react';
import { fetchSettingsStatus, updateKeys, uploadResumeBank } from '../api';
import type { SettingsStatus } from '../types';

export function SettingsPage() {
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  // Key form state
  const [serpapi, setSerpapi] = useState('');
  const [anthropic, setAnthropic] = useState('');
  const [gemini, setGemini] = useState('');
  const [provider, setProvider] = useState('gemini');

  // Resume bank file input
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadStatus();
  }, []);

  async function loadStatus() {
    try {
      const s = await fetchSettingsStatus();
      setStatus(s);
      setProvider(s.tailoring_provider);
    } catch {
      setMsg({ type: 'err', text: 'Failed to load settings' });
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveKeys() {
    setSaving(true);
    setMsg(null);
    try {
      const payload: Record<string, string> = { tailoring_provider: provider };
      if (serpapi) payload.serpapi_key = serpapi;
      if (anthropic) payload.anthropic_api_key = anthropic;
      if (gemini) payload.gemini_api_key = gemini;
      await updateKeys(payload);
      setSerpapi('');
      setAnthropic('');
      setGemini('');
      await loadStatus();
      setMsg({ type: 'ok', text: 'API keys updated.' });
    } catch (err) {
      setMsg({ type: 'err', text: `Failed to save keys: ${err}` });
    } finally {
      setSaving(false);
    }
  }

  async function handleUploadBank() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    setUploading(true);
    setMsg(null);
    try {
      const text = await file.text();
      const bank = JSON.parse(text);
      await uploadResumeBank(bank);
      await loadStatus();
      setMsg({ type: 'ok', text: 'Resume bank uploaded successfully.' });
    } catch (err) {
      setMsg({ type: 'err', text: `Upload failed: ${err}` });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="h-64 bg-bg-surface/50 rounded-xl animate-pulse" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
      {/* Message toast */}
      {msg && (
        <div
          className={`px-4 py-3 rounded-lg text-sm cursor-pointer ${
            msg.type === 'ok'
              ? 'bg-status-green/15 border border-status-green/30 text-status-green'
              : 'bg-status-red/15 border border-status-red/30 text-status-red'
          }`}
          onClick={() => setMsg(null)}
        >
          {msg.text}
        </div>
      )}

      {/* API Keys */}
      <section className="bg-bg-surface border border-border-subtle rounded-xl p-6">
        <h2 className="text-base font-semibold text-text-heading mb-4">API Keys</h2>
        <p className="text-xs text-text-body mb-4">
          Enter your own API keys. They are encrypted before storage. Leave a field blank to keep the existing key.
        </p>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-text-body mb-1">
              SerpAPI Key {status?.has_serpapi_key && <span className="text-status-green ml-1">configured</span>}
            </label>
            <input
              type="password"
              value={serpapi}
              onChange={e => setSerpapi(e.target.value)}
              placeholder={status?.has_serpapi_key ? '••••••••' : 'Enter SerpAPI key'}
              className="w-full bg-bg-primary border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-heading placeholder:text-text-body/40 focus:outline-none focus:border-accent-500"
            />
          </div>

          <div>
            <label className="block text-xs text-text-body mb-1">
              Anthropic API Key {status?.has_anthropic_key && <span className="text-status-green ml-1">configured</span>}
            </label>
            <input
              type="password"
              value={anthropic}
              onChange={e => setAnthropic(e.target.value)}
              placeholder={status?.has_anthropic_key ? '••••••••' : 'Enter Anthropic key'}
              className="w-full bg-bg-primary border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-heading placeholder:text-text-body/40 focus:outline-none focus:border-accent-500"
            />
          </div>

          <div>
            <label className="block text-xs text-text-body mb-1">
              Gemini API Key {status?.has_gemini_key && <span className="text-status-green ml-1">configured</span>}
            </label>
            <input
              type="password"
              value={gemini}
              onChange={e => setGemini(e.target.value)}
              placeholder={status?.has_gemini_key ? '••••••••' : 'Enter Gemini key'}
              className="w-full bg-bg-primary border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-heading placeholder:text-text-body/40 focus:outline-none focus:border-accent-500"
            />
          </div>

          <div>
            <label className="block text-xs text-text-body mb-1">Tailoring Provider</label>
            <select
              value={provider}
              onChange={e => setProvider(e.target.value)}
              className="bg-bg-primary border border-border-subtle rounded-lg px-3 py-2 text-sm text-text-heading focus:outline-none focus:border-accent-500"
            >
              <option value="gemini">Gemini</option>
              <option value="claude">Claude</option>
            </select>
          </div>
        </div>

        <button
          onClick={handleSaveKeys}
          disabled={saving}
          className="mt-4 px-4 py-2 bg-accent-500 hover:bg-accent-500/90 text-bg-primary text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Keys'}
        </button>
      </section>

      {/* Resume Bank */}
      <section className="bg-bg-surface border border-border-subtle rounded-xl p-6">
        <h2 className="text-base font-semibold text-text-heading mb-4">Resume Bank</h2>
        <p className="text-xs text-text-body mb-4">
          Upload your resume_bank.json file. This is used to generate tailored resumes.
          {status?.has_resume_bank && (
            <span className="text-status-green ml-1">Currently uploaded</span>
          )}
        </p>

        <div className="flex items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept=".json"
            className="text-sm text-text-body file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border file:border-border-subtle file:bg-bg-primary file:text-text-heading file:text-sm file:cursor-pointer hover:file:bg-bg-surface"
          />
          <button
            onClick={handleUploadBank}
            disabled={uploading}
            className="px-4 py-2 bg-accent-500 hover:bg-accent-500/90 text-bg-primary text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </div>
      </section>
    </div>
  );
}
