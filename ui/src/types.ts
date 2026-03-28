export interface ScoreBreakdown {
  title: number;
  yoe: number;
  location: number;
  company: number;
  recency: number;
  keywords: number;
  keyword_match_count: number;
  keyword_matched_skills: string[];
  keyword_missing_skills: string[];
  pass1_total: number;
  final_score: number;
}

export interface Job {
  dedup_key: string;
  title_raw: string;
  company: string;
  location: string;
  url: string;
  date_posted: string | null;
  first_seen_run: string;
  last_seen_run: string;
  times_seen: number;
  pass1_score: number | null;
  final_score: number | null;
  status: string;
  resume_path: string | null;
  jd_source: string | null;
  jd_word_count: number | null;
  title_experimental: boolean;
  query_source: string | null;
  score_breakdown: ScoreBreakdown | null;
  resume_status: string;
  resume_status_label: string;
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
  date_groups: string[];
}

export interface EligibleJob {
  dedup_key: string;
  title_raw: string;
  company: string;
  location: string;
  final_score: number | null;
}

export interface EligibleJobsResponse {
  jobs: EligibleJob[];
  total: number;
  threshold: number;
}

export interface PipelineEvent {
  stage: string;
  message: string;
  progress: number;
  data: Record<string, unknown> | null;
}

export interface Thresholds {
  generate_resume: number;
  include_in_digest: number;
}

// -- Manual job types -------------------------------------------------------

export interface ManualJobRequest {
  jd_text: string;
  url?: string;
  company?: string;
  title?: string;
}

export interface ManualJob {
  dedup_key: string;
  title_raw: string;
  company: string;
  url: string;
  jd_word_count: number | null;
  created_at: string | null;
  resume_status: string;
  resume_status_label: string;
  resume_path: string | null;
  source: string;
}

export interface ManualJobListResponse {
  jobs: ManualJob[];
  total: number;
}

// -- Auth types -------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  name: string;
  picture: string | null;
}

export interface AuthState {
  jwt: string | null;
  user: User | null;
  loading: boolean;
}

export interface SettingsStatus {
  has_serpapi_key: boolean;
  has_anthropic_key: boolean;
  has_gemini_key: boolean;
  has_resume_bank: boolean;
  tailoring_provider: string;
}

export interface ClientConfig {
  google_client_id: string;
}
