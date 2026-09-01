// Type shapes matching /api/* JSON responses.

export type KeyStatus = {
  env_var: string;
  service: string;
  placeholder: string;
  is_set: boolean;
  masked: string | null;
};

export type RefTag = { name: string; count: number };
export type RefItem = {
  id: string;
  name: string;
  ext: string;
  size_kb: number;
  rel_url: string;
  tags: string[];
};

export type Brand = {
  id: number;
  name: string;
  tagline: string;
  audience: string;
  palette: string[];
  typography: string;
  voice: string;
  do_examples: string;
  dont_examples: string;
  style_guide: string;
  created_at: number;
  updated_at: number;
};

export type Draft = {
  id: number;
  name: string;
  body: string;
  category: string;
  is_favorite: boolean;
  created_at: number;
  updated_at: number;
};

export type Job = {
  id: string;
  status:
    | "pending"
    | "running"
    | "succeeded"
    | "failed"
    | "cancelled";
  prompt: string;
  effective_prompt: string | null;
  model: string;
  duration: number;
  resolution: string;
  reference: string | null;
  references: string[] | null;
  ref_ids: string[];
  draft_id: number | null;
  brand_id: number | null;
  batch_id: string | null;
  output_rel: string | null;
  elapsed_seconds: number | null;
  cost_usd: number | null;
  error: string | null;
};

export type BatchSummary = {
  batch_id: string;
  total: number;
  succeeded: number;
  failed: number;
  running: number;
};

export type OutputItem = {
  id: string;
  rel_url: string;
  size_mb: number;
  created: number;
  prompt: string | null;
  brand_name: string | null;
  draft_name: string | null;
  refs: { id: string; name: string; rel_url: string }[];
};

// A fal.ai model surfaced by /api/models.
export type ModelSpec = {
  id: string;
  name: string;
  category: "video" | "image";
  vendor: string;
  description: string;
  durations: number[];
  resolutions: string[];
  aspect_ratios: string[];
  per_second_usd: Record<string, number>;
  per_image_usd: number;
  badge: string;
  is_default: boolean;
};

// An image generation job (separate from video Job so output_paths is plural).
export type ImageJob = {
  job_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  prompt: string;
  model: string;
  aspect_ratio: string;
  num_images: number;
  ref_ids: string[];
  brand_id: number | null;
  draft_id: number | null;
  output_paths: string[];
  output_rel: string | null;
  cost_usd: number | null;
  elapsed_seconds: number | null;
  error: string | null;
  created_at: number;
  updated_at: number;
};

export type CostEstimate = {
  usd: number;
  model_id: string;
  category: "video" | "image";
  duration?: number;
  resolution?: string;
  aspect_ratio?: string;
  num_images?: number;
  note?: string;
};
