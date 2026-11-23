// Response/request types — snake_case to match the backend VO/AO exactly.

export interface UpstreamKey {
  id: string;
  label: string;
  secret_masked: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
  last_error_status: number | null;
  consecutive_failures: number;
  secret?: string; // only on creation
}

export interface ClientKey {
  id: string;
  name: string;
  secret_masked: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  secret?: string;
}

export interface RequestLog {
  id: string;
  ts: string;
  client_key_id: string | null;
  client_key_name: string | null;
  upstream_key_id: string | null;
  upstream_key_label: string | null;
  method: string;
  path: string;
  model: string | null;
  status: number;
  latency_ms: number;
  stream: boolean;
  prompt_tokens: number | null;
  completion_tokens: number | null;
}

export interface Usage {
  bucket: string;
  bucket_type: string;
  dimension_type: string;
  dimension_value: string;
  requests: number;
  errors: number;
  rate_limited: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface Dashboard {
  status: string;
  upstream: string;
  auth_mode: string;
  upstream_key_count: number;
  client_key_count: number;
  today: { requests: number; errors: number; rate_limited: number };
}

export interface ConfigView {
  upstream: string;
  connect_timeout: number;
  read_timeout: number;
  auth_mode: string;
  port: number;
  db_backend: string;
}

export interface Page<T> {
  records: T[];
  total: number;
  page_num: number;
  page_size: number;
}
