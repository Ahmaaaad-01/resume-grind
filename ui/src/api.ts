import type {
  JobListResponse, EligibleJobsResponse, PipelineEvent, Thresholds,
  ManualJobRequest, ManualJob, ManualJobListResponse,
  User, SettingsStatus, ClientConfig,
} from './types';

const BASE = '';

// ---------------------------------------------------------------------------
// Auth token management
// ---------------------------------------------------------------------------

let _authToken: string | null = localStorage.getItem('jwt');

export function setAuthToken(token: string | null) {
  _authToken = token;
  if (token) {
    localStorage.setItem('jwt', token);
  } else {
    localStorage.removeItem('jwt');
  }
}

export function getAuthToken(): string | null {
  return _authToken;
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (_authToken) {
    headers['Authorization'] = `Bearer ${_authToken}`;
  }
  return headers;
}

async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = { ...authHeaders(), ...(init.headers as Record<string, string> || {}) };
  return fetch(url, { ...init, headers });
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export async function fetchClientConfig(): Promise<ClientConfig> {
  const res = await fetch(`${BASE}/api/config/client`);
  if (!res.ok) throw new Error(`Failed to fetch client config: ${res.status}`);
  return res.json();
}

export async function googleAuth(idToken: string): Promise<{ jwt: string; user: User }> {
  const res = await fetch(`${BASE}/api/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: idToken }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Auth failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchMe(): Promise<User> {
  const res = await authFetch(`${BASE}/api/auth/me`);
  if (!res.ok) throw new Error(`Not authenticated`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Settings API
// ---------------------------------------------------------------------------

export async function fetchSettingsStatus(): Promise<SettingsStatus> {
  const res = await authFetch(`${BASE}/api/settings/status`);
  if (!res.ok) throw new Error(`Failed to fetch settings: ${res.status}`);
  return res.json();
}

export async function updateKeys(keys: {
  serpapi_key?: string;
  anthropic_api_key?: string;
  gemini_api_key?: string;
  tailoring_provider?: string;
}): Promise<void> {
  const res = await authFetch(`${BASE}/api/settings/keys`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(keys),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Failed to update keys: ${res.status}`);
  }
}

export async function uploadResumeBank(resumeBank: object): Promise<void> {
  const res = await authFetch(`${BASE}/api/settings/resume-bank`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_bank: resumeBank }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Failed to upload resume bank: ${res.status}`);
  }
}

export async function fetchResumeBank(): Promise<object> {
  const res = await authFetch(`${BASE}/api/settings/resume-bank`);
  if (!res.ok) throw new Error(`No resume bank found`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Jobs API
// ---------------------------------------------------------------------------

export async function fetchJobs(days = 7, includeExpired = false): Promise<JobListResponse> {
  const params = new URLSearchParams({ days: String(days), include_expired: String(includeExpired) });
  const res = await authFetch(`${BASE}/api/jobs?${params}`);
  if (!res.ok) throw new Error(`Failed to fetch jobs: ${res.status}`);
  return res.json();
}

export async function fetchEligibleJobs(): Promise<EligibleJobsResponse> {
  const res = await authFetch(`${BASE}/api/jobs/eligible`);
  if (!res.ok) throw new Error(`Failed to fetch eligible jobs: ${res.status}`);
  return res.json();
}

export async function fetchThresholds(): Promise<Thresholds> {
  const res = await authFetch(`${BASE}/api/config/thresholds`);
  if (!res.ok) throw new Error(`Failed to fetch thresholds: ${res.status}`);
  return res.json();
}

export function resumeDownloadUrl(dedupKey: string): string {
  const token = getAuthToken();
  const params = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${BASE}/api/resumes/${dedupKey}/download${params}`;
}

export function resumePreviewUrl(dedupKey: string): string {
  const token = getAuthToken();
  const params = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${BASE}/api/resumes/${dedupKey}/preview${params}`;
}

// -- Manual job API ---------------------------------------------------------

export async function fetchManualJobs(): Promise<ManualJobListResponse> {
  const res = await authFetch(`${BASE}/api/manual-jobs`);
  if (!res.ok) throw new Error(`Failed to fetch manual jobs: ${res.status}`);
  return res.json();
}

export async function submitManualJob(request: ManualJobRequest): Promise<ManualJob> {
  const res = await authFetch(`${BASE}/api/manual-jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Submit failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteManualJob(dedupKey: string): Promise<void> {
  const res = await authFetch(`${BASE}/api/manual-jobs/${dedupKey}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
}

export async function regenerateManualJob(dedupKey: string): Promise<ManualJob> {
  const res = await authFetch(`${BASE}/api/manual-jobs/${dedupKey}/regenerate`, { method: 'POST' });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Regenerate failed: ${res.status}`);
  }
  return res.json();
}

// -- Pipeline API -----------------------------------------------------------

export function subscribePipeline(
  endpoint: string,
  body: unknown | null,
  onEvent: (event: PipelineEvent) => void,
  onDone: () => void,
  onError: (err: string) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const headers: Record<string, string> = { ...authHeaders() };
      if (body) headers['Content-Type'] = 'application/json';

      const res = await fetch(`${BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!res.ok) {
        onError(`Pipeline request failed: ${res.status}`);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) { onError('No response body'); return; }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data:')) {
            const json = line.slice(5).trim();
            if (!json) continue;
            try {
              const event: PipelineEvent = JSON.parse(json);
              onEvent(event);
              if (event.stage === 'done' || event.stage === 'error') {
                onDone();
                return;
              }
            } catch {
              // skip malformed SSE lines
            }
          }
        }
      }
      onDone();
    } catch (err) {
      if (!controller.signal.aborted) {
        onError(String(err));
      }
    }
  })();

  return () => controller.abort();
}
