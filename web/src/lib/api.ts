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
      // ignore, keep status text
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

  // ----- Phase A: pipelines -----
  listNodeSchemas: () =>
    call<Ok<import("./types").NodeSchemaResponse>>("/api/pipelines/node-schemas"),

  listPipelines: () =>
    call<Ok<{ pipelines: import("./types").Pipeline[] }>>("/api/pipelines"),

  createPipeline: (data: {
    name: string;
    description?: string;
    nodes: import("./types").PipelineNode[];
    edges: import("./types").PipelineEdge[];
    max_workers?: number;
    enabled?: boolean;
  }) =>
    call<Ok<{ pipeline: import("./types").Pipeline }>>("/api/pipelines", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getPipeline: (id: number) =>
    call<Ok<{ pipeline: import("./types").Pipeline }>>(`/api/pipelines/${id}`),

  updatePipeline: (
    id: number,
    data: Partial<{
      name: string;
      description: string;
      nodes: import("./types").PipelineNode[];
      edges: import("./types").PipelineEdge[];
      max_workers: number;
      enabled: boolean;
    }>,
  ) =>
    call<Ok<{ pipeline: import("./types").Pipeline }>>(`/api/pipelines/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deletePipeline: (id: number) =>
    call<Ok<{ deleted: true }>>(`/api/pipelines/${id}`, { method: "DELETE" }),

  runPipeline: (id: number, triggered_by?: string) =>
    call<Ok<{ run: import("./types").PipelineRun }>>(
      `/api/pipelines/${id}/run`,
      {
        method: "POST",
        body: JSON.stringify({ triggered_by: triggered_by ?? "ui" }),
      },
    ),

  listPipelineRuns: (id: number) =>
    call<Ok<{ runs: import("./types").PipelineRun[] }>>(
      `/api/pipelines/${id}/runs`,
    ),

  getPipelineRun: (runId: number) =>
    call<Ok<{ run: import("./types").PipelineRun }>>(
      `/api/pipelines/runs/${runId}`,
    ),

  // ---- Phase D: extensions ----
  listExtensions: () =>
    call<Ok<{ extensions: import("./types").Extension[] }>>("/api/extensions"),

  enableExtension: (id: string, secret?: string) =>
    call<Ok<{ id: string; enabled: boolean }>>(
      `/api/extensions/${encodeURIComponent(id)}/enable`,
      { method: "POST", body: JSON.stringify({ secret: secret ?? "" }) },
    ),

  disableExtension: (id: string) =>
    call<Ok<{ id: string; enabled: boolean }>>(
      `/api/extensions/${encodeURIComponent(id)}/disable`,
      { method: "POST" },
    ),
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

// ----- Phase A: Brand-poster surface -----

export const brandPoster = {
  // Templates
  listTemplates: (params?: { brand_id?: number; category?: string }) => {
    const qs = new URLSearchParams();
    if (params?.brand_id) qs.set("brand_id", String(params.brand_id));
    if (params?.category) qs.set("category", params.category);
    const q = qs.toString();
    return call<
      Ok<{
        templates: import("./types").Template[];
        aspect_ratios: string[];
        layer_types: string[];
      }>
    >(`/api/templates${q ? `?${q}` : ""}`);
  },
  getTemplate: (id: number) =>
    call<Ok<{ template: import("./types").Template }>>(`/api/templates/${id}`),
  createTemplate: (data: Partial<import("./types").Template>) =>
    call<Ok<{ template_id: number }>>(`/api/templates`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateTemplate: (id: number, data: Partial<import("./types").Template>, force = false) =>
    call<Ok<{ updated: boolean }>>(`/api/templates/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ ...data, force }),
    }),
  deleteTemplate: (id: number, force = false) =>
    call<Ok<{ deleted: boolean }>>(`/api/templates/${id}?force=${force ? 1 : 0}`, {
      method: "DELETE",
    }),
  duplicateTemplate: (id: number, name: string) =>
    call<Ok<{ template_id: number }>>(`/api/templates/${id}/duplicate`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  bootBuiltins: () =>
    call<Ok<{ inserted: number }>>(`/api/templates/boot-builtins`, {
      method: "POST",
    }),

  // Products
  listProducts: (params?: { brand_id?: number; category?: string; collection?: string; tag?: string }) => {
    const qs = new URLSearchParams();
    if (params?.brand_id) qs.set("brand_id", String(params.brand_id));
    if (params?.category) qs.set("category", params.category);
    if (params?.collection) qs.set("collection", params.collection);
    if (params?.tag) qs.set("tag", params.tag);
    const q = qs.toString();
    return call<Ok<{ products: import("./types").Product[] }>>(`/api/products${q ? `?${q}` : ""}`);
  },
  getProduct: (id: number) =>
    call<Ok<{ product: import("./types").Product; variants: unknown[] }>>(`/api/products/${id}`),
  createProduct: (data: Partial<import("./types").Product>) =>
    call<Ok<{ product_id: number }>>(`/api/products`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateProduct: (id: number, data: Partial<import("./types").Product>) =>
    call<Ok<{ updated: boolean }>>(`/api/products/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteProduct: (id: number) =>
    call<Ok<{ deleted: boolean }>>(`/api/products/${id}`, { method: "DELETE" }),
  importProducts: (data: { brand_id?: number; rows?: unknown[]; csv?: string }) =>
    call<Ok<{ imported: number; skipped: number; errors: string[] }>>(`/api/products/import`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  requestCutout: (id: number, regenerate = false) =>
    call<Ok<{ cutout_path: string }>>(`/api/products/${id}/cutout?regenerate=${regenerate ? 1 : 0}`, {
      method: "POST",
    }),

  // Filters
  listFilters: () =>
    call<
      Ok<{
        presets: import("./types").FilterPreset[];
        user: import("./types").UserFilterPreset[];
      }>
    >(`/api/filters`),
  previewFilter: (image_path: string, settings: Record<string, number>) =>
    call<Ok<{ preview_path: string }>>(`/api/filters/preview`, {
      method: "POST",
      body: JSON.stringify({ image_path, settings }),
    }),

  // Render
  render: (data: {
    template_id: number;
    product_id?: number | null;
    filter?: string;
    aspect_ratio?: string;
    intensity?: number;
    layer_overrides?: Record<string, unknown>;
    brand_id?: number | null;
  }) =>
    call<Ok<import("./types").RenderResult>>(`/api/render`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  renderBatch: (data: {
    template_id: number;
    product_ids: number[];
    filter?: string;
    intensity?: number;
  }) =>
    call<
      Ok<{ renders: import("./types").RenderResult[] }>
    >(`/api/render/batch`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Outputs gallery
  listImageOutputs: () =>
    call<Ok<{ outputs: import("./types").OutputRow[] }>>(`/api/outputs/images`),
};

export const video = {
  listTemplates: () =>
    call<Ok<{ templates: { name: string; template: Record<string, unknown> }[] }>>(
      `/api/video/templates`,
    ),
  render: (data: {
    template_id: number;
    product_id?: number | null;
    brand_id?: number | null;
    audio_track?: { path: string } | null;
  }) =>
    call<Ok<{
      output_id: number;
      file_path: string;
      rel_url: string | null;
      duration_s: number;
      cost_usd: number;
      elapsed_seconds: number;
    }>>(`/api/video/render`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  oneShot: (data: {
    brief: string;
    product_id: number;
    template_id?: number | null;
    duration_s?: number;
    brand?: Record<string, unknown>;
  }) =>
    call<Ok<{
      output_id: number;
      file_path: string;
      rel_url: string | null;
      duration_s: number;
      cost_usd: number;
      elapsed_seconds: number;
    }>>(`/api/video/one-shot`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ----- Phase F: Studio Pro -----

export interface StudioProSuggestion {
  id?: number;
  template_id: number | null;
  layer_overrides: Record<string, unknown>;
  rationale: string;
  platforms: string[];
  duration_s?: number | null;
  cost_usd: number;
  confidence_score: number;
}

export interface StudioProAgentLog {
  agent: string;
  started_at?: number;
  finished_at?: number;
  status: "running" | "ok" | "error";
  outputs?: string[];
  note?: string;
  error?: string;
}

export interface StudioProBrief {
  brief: string;
  product_id: number | null;
  brand_id: number | null;
  platforms: string[];
  budget_usd: number;
  audience?: string | null;
  duration_s?: number | null;
}

export const studioPro = {
  generate: (brief: StudioProBrief) =>
    call<Ok<{
      run_id: string;
      suggestions: StudioProSuggestion[];
      agent_log: StudioProAgentLog[];
      spent_usd: number;
      started_at: number;
      finished_at: number;
    }>>(`/api/studio-pro/generate`, {
      method: "POST",
      body: JSON.stringify(brief),
    }),
  log: (runId: string) =>
    call<Ok<{
      run_id: string;
      suggestions: Array<StudioProSuggestion & { id: number }>;
    }>>(`/api/studio-pro/${encodeURIComponent(runId)}/log`),
  accept: (suggestionId: number, body: { product_id: number | null; brand_id: number | null }) =>
    call<Ok<{
      suggestion_id: number;
      output_id: number;
      editor_url: string;
      file_path: string;
    }>>(`/api/studio-pro/${suggestionId}/accept`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  schedule: (
    suggestionId: number,
    body: { run_at: number; platform?: string }
  ) =>
    call<Ok<{ suggestion_id: number; job_id: number }>>(
      `/api/studio-pro/${suggestionId}/schedule`,
      {
        method: "POST",
        body: JSON.stringify(body),
      }
    ),
};

// ----- Phase G: presets, automation, config -----

export interface Preset {
  id: number;
  brand_id: number | null;
  name: string;
  description: string | null;
  template_id: number | null;
  filter: string | null;
  caption_template: string | null;
  layers: Array<Record<string, unknown>>;
  product_filter: Record<string, unknown>;
  schedule_settings: Record<string, unknown>;
  created_at: number;
}

export interface AutomationRule {
  id: number;
  brand_id: number | null;
  name: string;
  trigger: string;
  conditions: Array<{ field: string; op: string; value: unknown }>;
  action: { kind: string; [k: string]: unknown };
  is_active: boolean;
  last_run: number | null;
  created_at: number;
}

export const phaseG = {
  listPresets: (brandId?: number | null) => {
    const qs = brandId ? `?brand_id=${brandId}` : "";
    return call<Ok<{ presets: Preset[] }>>(`/api/presets${qs}`);
  },
  createPreset: (body: {
    brand_id: number | null;
    name: string;
    description?: string | null;
    template_id?: number | null;
    filter?: string | null;
    product_filter?: Record<string, unknown>;
  }) =>
    call<Ok<{ preset_id: number }>>("/api/presets", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deletePreset: (id: number) =>
    call<Ok<{ deleted: boolean }>>(`/api/presets/${id}`, {
      method: "DELETE",
    }),
  applyPreset: (presetId: number, productIds: number[]) =>
    call<Ok<{ queued: number; output_ids: number[]; errors: string[] }>>(
      `/api/presets/${presetId}/apply`,
      {
        method: "POST",
        body: JSON.stringify({ product_ids: productIds }),
      }
    ),
  listAutomationRules: (brandId?: number | null) => {
    const qs = brandId ? `?brand_id=${brandId}` : "";
    return call<Ok<{ rules: AutomationRule[] }>>(
      `/api/automation/rules${qs}`
    );
  },
  createAutomationRule: (body: {
    brand_id: number | null;
    name: string;
    trigger: string;
    conditions: AutomationRule["conditions"];
    action: AutomationRule["action"];
    is_active?: boolean;
  }) =>
    call<Ok<{ rule_id: number }>>("/api/automation/rules", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  toggleAutomationRule: (id: number, isActive: boolean) =>
    call<Ok<{ rule: AutomationRule }>>(
      `/api/automation/rules/${id}`,
      {
        method: "PATCH",
        body: JSON.stringify({ is_active: isActive }),
      }
    ),
  deleteAutomationRule: (id: number) =>
    call<Ok<{ deleted: boolean }>>(`/api/automation/rules/${id}`, {
      method: "DELETE",
    }),
  exportConfig: () => call<Ok<{ config: unknown }>>("/api/config/export"),
  importConfig: (config: unknown, merge = true) =>
    call<Ok<{ imported: Record<string, number> }>>("/api/config/import", {
      method: "POST",
      body: JSON.stringify({ config, merge }),
    }),
};
