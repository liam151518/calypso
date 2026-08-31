/**
 * Browser-side API client.
 *
 * Routes are proxied to the FastAPI backend by next.config.mjs.
 * If the backend isn't running, callers should gracefully show an offline state.
 */

const BASE = "/api/backend";

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

async function postJson<T>(path: string, body?: unknown): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export const api = {
  overview: () => getJson<Overview>("/overview"),
  phases: () => getJson<Phase[]>("/phases"),
  scripts: () => getJson<ScriptInfo[]>("/scripts"),
  brandPack: () => getJson<BrandFile[]>("/brand"),
  workflows: () => getJson<WorkflowInfo[]>("/workflows"),
  tests: () => getJson<TestSummary>("/tests"),
  testsRun: () => postJson<TestRunResult>("/tests/run"),
  verifyRun: () => postJson<VerifyRunResult>("/verify/run"),
  accounts: () => getJson<Account[]>("/accounts"),
  scriptRun: (name: string, args: string[] = []) =>
    postJson<ScriptRunResult>(`/scripts/run`, { name, args }),
  adamStatus: () => getJson<AdamStatus>("/adam/status"),
  adamCalibrate: () => postJson<{ ok: boolean; message: string }>("/adam/calibrate"),
};

export interface Overview {
  tests_pass: number;
  tests_total: number;
  verify_pass: number;
  verify_fail: number;
  verify_skip: number;
  scripts: number;
  workflows: number;
  brand_files: number;
  references: number;
  adam_installed: boolean;
  api_offline: boolean;
}

export interface Phase {
  id: string;
  name: string;
  status: "done" | "in_progress" | "pending";
  summary: string;
  deliverables: string[];
}

export interface ScriptInfo {
  name: string;
  path: string;
  has_cli: boolean;
  description: string;
}

export interface BrandFile {
  path: string;
  size: number;
  preview?: string;
}

export interface WorkflowInfo {
  name: string;
  path: string;
  nodes: number;
  triggers: string[];
}

export interface TestSummary {
  total: number;
  passed: number;
  failed: number;
  files: { file: string; passed: number; failed: number }[];
}

export interface TestRunResult {
  ok: boolean;
  duration_ms: number;
  passed: number;
  failed: number;
  output_tail: string;
}

export interface VerifyRunResult {
  ok: boolean;
  pass: number;
  fail: number;
  skip: number;
  output_tail: string;
}

export interface Account {
  name: string;
  url: string;
  purpose: string;
  required: boolean;
  env_key: string;
  env_present: boolean;
}

export interface ScriptRunResult {
  ok: boolean;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_ms: number;
}

export interface AdamStatus {
  installed_at_user_level: boolean;
  installed_at_project_level: boolean;
  user_skills: string[];
  project_skills: string[];
  context_files: string[];
  ready: boolean;
}
