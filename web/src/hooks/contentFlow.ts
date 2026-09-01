import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type CaptionVariant = {
  content: string;
  hashtags: string[];
  first_comment: string;
  alt_text: string;
};

export type FeedItem = {
  id: number;
  brand_id: number | null;
  product_id: number | null;
  template_id: number | null;
  type: string | null;
  aspect_ratio: string | null;
  status: string | null;
  filter_applied: string | null;
  created_at: number;
  rel_url: string | null;
  thumb_url: string | null;
};

export type ScheduledJob = {
  id: number;
  name: string;
  kind: string;
  payload: Record<string, unknown>;
  run_at: number;
  status: string;
  last_error: string;
  created_at: number;
};

export const contentFlowKeys = {
  captionsFor: (outputId: number) => ["captions", outputId] as const,
  feed: (brandId: number | null | undefined, newId: number | null | undefined) =>
    ["feed", brandId ?? null, newId ?? null] as const,
  jobs: (status: string | null | undefined) => ["scheduler", "jobs", status ?? null] as const,
  publishers: ["publishers"] as const,
};

// ---- Captions ----

async function generateCaptions(input: {
  product_id: number;
  template_id: number;
  brand_id?: number | null;
  platform?: string;
  model?: string;
  count?: number;
}): Promise<{ variants: CaptionVariant[] }> {
  const res = await fetch("/api/captions/generate", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    throw new Error(j?.error ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function useGenerateCaptions() {
  return useMutation({
    mutationFn: generateCaptions,
  });
}

async function selectCaption(input: {
  output_id: number;
  variant: CaptionVariant;
  platform?: string;
  brand_id?: number | null;
  template_id?: number | null;
  product_id?: number | null;
}) {
  const res = await fetch("/api/captions/select", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ caption_id: number }>;
}

export function useSelectCaption() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: selectCaption,
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: contentFlowKeys.captionsFor(vars.output_id) });
    },
  });
}

export function useCaptionsFor(outputId: number | null | undefined) {
  return useQuery({
    queryKey: outputId ? contentFlowKeys.captionsFor(outputId) : ["captions", "none"],
    queryFn: async () => {
      if (!outputId) return { captions: [] };
      const res = await fetch(`/api/captions/${outputId}`);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json() as Promise<{ captions: unknown[] }>;
    },
    enabled: !!outputId,
  });
}

// ---- Feed grid ----

async function fetchFeed(brand_id?: number | null, new_output_id?: number | null) {
  const qs = new URLSearchParams();
  if (brand_id) qs.set("brand_id", String(brand_id));
  if (new_output_id) qs.set("new_output_id", String(new_output_id));
  const url = "/api/feed" + (qs.toString() ? `?${qs}` : "");
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<{ items: FeedItem[] }>;
}

export function useFeed(brand_id?: number | null, new_output_id?: number | null) {
  return useQuery({
    queryKey: contentFlowKeys.feed(brand_id, new_output_id),
    queryFn: () => fetchFeed(brand_id, new_output_id),
  });
}

export function useShuffleFeed() {
  return useMutation({
    mutationFn: async (input: { brand_id?: number | null; request_token?: string }) => {
      const res = await fetch("/api/feed/shuffle", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(input),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json() as Promise<{ items: FeedItem[] }>;
    },
  });
}

// ---- Scheduler ----

async function scheduleJob(input: {
  name: string;
  kind?: string;
  run_at: number;
  payload?: Record<string, unknown>;
}) {
  const res = await fetch("/api/scheduler/schedule", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ kind: "publish_output", ...input }),
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<{ job_id: number }>;
}

export function useSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: scheduleJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scheduler", "jobs"] }),
  });
}

export function useSchedulerJobs(status?: string | null) {
  return useQuery({
    queryKey: contentFlowKeys.jobs(status),
    queryFn: async () => {
      const url = "/api/scheduler/jobs" + (status ? `?status=${status}` : "");
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json() as Promise<{ jobs: ScheduledJob[] }>;
    },
    refetchInterval: 10_000,
  });
}

export function useRunNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (jobId: number) => {
      const res = await fetch(`/api/scheduler/jobs/${jobId}/run`, { method: "POST" });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scheduler", "jobs"] }),
  });
}

export function useCancelJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (jobId: number) => {
      const res = await fetch(`/api/scheduler/jobs/${jobId}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scheduler", "jobs"] }),
  });
}

export function useApproveJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (jobId: number) => {
      const res = await fetch(`/api/scheduler/jobs/${jobId}/approve`, { method: "POST" });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scheduler", "jobs"] }),
  });
}

// ---- Publishers ----

export function usePublishers() {
  return useQuery({
    queryKey: contentFlowKeys.publishers,
    queryFn: async () => {
      const res = await fetch("/api/publishers");
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json() as Promise<{ publishers: string[] }>;
    },
  });
}

export function useDispatch() {
  return useMutation({
    mutationFn: async (input: { output_id: number; platform: string; preferred?: string }) => {
      const res = await fetch("/api/publishers/dispatch", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(input),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return res.json() as Promise<{ publisher: { external_id: string; url: string | null; status: string } }>;
    },
  });
}