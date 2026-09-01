// Typed fetch client that hits the Flask JSON endpoints.
// All methods throw on non-ok responses so React Query can retry / surface errors.

export type Ok<T> = { ok: true } & T;
export type ApiError = { ok: false; error: string; status: number };

const BASE = "";

async function call<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(BASE + path, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(init.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(init.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (j?.error) msg = j.error;
    } catch {
      // ignore — keep status text
    }
    throw new Error(msg);
  }
  // Some endpoints return 204.
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => call<{ status: string; service: string; version: string }>("/api/health"),

  // Keys
  listKeys: () => call<Ok<{ keys: import("./types").KeyStatus[] }>>("/api/keys"),
  setKey: (env_var: string, value: string) =>
    call<Ok<{ env_var: string }>>(`/api/keys/${env_var}`, {
      method: "POST",
      body: JSON.stringify({ value }),
    }),
  deleteKey: (env_var: string) =>
    call<Ok<{ deleted: string }>>(`/api/keys/${env_var}`, { method: "DELETE" }),

  // Refs
  listRefs: () =>
    call<
      Ok<{
        refs: import("./types").RefItem[];
        tags: import("./types").RefTag[];
      }>
    >("/api/refs"),
  uploadRef: (file: File, tags: string[]) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("tags", tags.join(","));
    return call<Ok<{ ref: import("./types").RefItem }>>("/api/refs", {
      method: "POST",
      body: fd,
    });
  },
  setRefTags: (id: string, tags: string[]) =>
    call<Ok<{ id: string; tags: string[] }>>(`/api/refs/${id}/tags`, {
      method: "PATCH",
      body: JSON.stringify({ tags: tags.join(",") }),
    }),
  deleteRef: (id: string) =>
    call<Ok<{ deleted: string }>>(`/api/refs/${id}`, { method: "DELETE" }),

  // Brands
  listBrands: () =>
    call<
      Ok<{
        brands: import("./types").Brand[];
        active: import("./types").Brand | null;
      }>
    >("/api/brands"),
  createBrand: (data: Partial<import("./types").Brand>) =>
    call<Ok<{ brand: import("./types").Brand }>>("/api/brands", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateBrand: (id: number, data: Partial<import("./types").Brand>) =>
    call<Ok<{ brand: import("./types").Brand }>>(`/api/brands/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteBrand: (id: number) =>
    call<Ok<{ deleted: number }>>(`/api/brands/${id}`, { method: "DELETE" }),
  activateBrand: (id: number) =>
    call<Ok<{ active_brand_id: number }>>(`/api/brands/${id}/activate`, {
      method: "POST",
    }),
  clearActiveBrand: () =>
    call<Ok<{ active_brand_id: null }>>("/api/brands/active", { method: "DELETE" }),

  // Drafts
  listDrafts: (params?: {
    query?: string;
    category?: string;
    favorites_only?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params?.query) qs.set("query", params.query);
    if (params?.category) qs.set("category", params.category);
    if (params?.favorites_only) qs.set("favorites_only", "1");
    const q = qs.toString();
    return call<
      Ok<{
        drafts: import("./types").Draft[];
        categories: { category: string; count: number }[];
      }>
    >(`/api/drafts${q ? `?${q}` : ""}`);
  },
  createDraft: (data: Partial<import("./types").Draft>) =>
    call<Ok<{ draft: import("./types").Draft }>>("/api/drafts", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  deleteDraft: (id: number) =>
    call<Ok<{ deleted: number }>>(`/api/drafts/${id}`, { method: "DELETE" }),
  favoriteDraft: (id: number) =>
    call<Ok<{ draft_id: number }>>(`/api/drafts/${id}/favorite`, { method: "POST" }),

  // Jobs
  generate: (data: {
    prompt: string;
    model?: string;
    duration?: number;
    resolution?: string;
    ref_ids?: string[];
    draft_id?: number | null;
    brand_id?: number | null;
  }) => {
    const fd = new FormData();
    fd.append("prompt", data.prompt);
    fd.append("model", data.model ?? "auto");
    fd.append("duration", String(data.duration ?? 8));
    fd.append("resolution", data.resolution ?? "768p");
    if (data.draft_id) fd.append("draft_id", String(data.draft_id));
    if (data.brand_id) fd.append("brand_id", String(data.brand_id));
    for (const r of data.ref_ids ?? []) fd.append("ref_ids", r);
    return call<
      Ok<{
        kind: "job" | "batch";
        job?: import("./types").Job;
        batch_id?: string;
        jobs?: import("./types").Job[];
      }>
    >("/api/generate", { method: "POST", body: fd });
  },
  listJobs: () =>
    call<Ok<{ jobs: import("./types").Job[] }>>("/api/jobs"),
  getJob: (id: string) =>
    call<Ok<{ job: import("./types").Job }>>(`/api/jobs/${id}`),

  // Outputs
  listOutputs: () =>
    call<Ok<{ outputs: import("./types").OutputItem[] }>>("/api/outputs"),

  // Models + cost estimates
  listModels: () =>
    call<
      Ok<{
        models: import("./types").ModelSpec[];
        defaults: { video: string; image: string };
      }>
    >("/api/models"),
  estimateCost: (data: {
    model: string;
    duration?: number;
    resolution?: string;
    aspect_ratio?: string;
    num_images?: number;
  }) =>
    call<Ok<{ estimate: import("./types").CostEstimate }>>("/api/cost-estimate", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Image jobs
  generateImage: (data: {
    prompt: string;
    model: string;
    aspect_ratio: string;
    num_images: number;
    ref_id?: string | null;
    draft_id?: number | null;
    brand_id?: number | null;
  }) =>
    call<Ok<{ job: import("./types").ImageJob }>>("/api/image-generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listImageJobs: () =>
    call<Ok<{ jobs: import("./types").ImageJob[] }>>("/api/image-jobs"),
  getImageJob: (id: string) =>
    call<Ok<{ job: import("./types").ImageJob }>>(`/api/image-jobs/${id}`),

  listImageOutputs: () =>
    call<Ok<{ outputs: ImageOutputItem[] }>>("/api/image-outputs"),
};

export type ImageOutputItem = {
  id: string;
  job_id: string;
  rel_url: string;
  size_mb: number;
  created: number;
  prompt: string;
  model: string;
  aspect_ratio: string;
  num_images: number;
  cost_usd: number | null;
};
