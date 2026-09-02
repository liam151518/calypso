// Type shapes matching /api/* JSON responses.

export type KeyStatus = {
  env_var: string;
  service: string;
  placeholder: string;
  group: string;
  required: boolean;
  docs_url: string | null;
  description: string;
  is_set: boolean;
  masked: string | null;
  is_custom?: boolean;
};

export type KeysResponse = {
  keys: KeyStatus[];
  custom: KeyStatus[];
  groups: { name: string; keys: string[] }[];
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

// ----- Phase A: Pipeline / Funnel builder -----

export type PipelineNode = {
  id: string;
  type: string; // e.g. "trigger", "model", "generate"
  params: Record<string, unknown>;
  position?: { x: number; y: number };
};

export type PipelineEdge = {
  source: string;
  target: string;
  source_port?: string;
  target_port?: string;
};

export type Pipeline = {
  id: number;
  name: string;
  description: string;
  nodes: PipelineNode[];
  edges: PipelineEdge[];
  max_workers: number;
  enabled: boolean;
  created_at: number;
  updated_at: number;
};

export type PipelineRun = {
  id: number;
  pipeline_id: number;
  status: "queued" | "running" | "succeeded" | "failed";
  log: Array<{ t: number; node: string; msg: string }>;
  started_at: number | null;
  finished_at: number | null;
  spent_usd: number;
  error: string | null;
  triggered_by: string | null;
};

export type NodeSchema = {
  title: string;
  category: string;
  description: string;
  inputs?: string[];
  outputs?: string[];
  params: Record<string, unknown>;
};

export type NodeSchemaResponse = {
  schemas: Record<string, NodeSchema>;
  categories: Record<string, string[]>;
};

export type Extension = {
  id: string;
  version: string;
  type: string;
  name: string;
  author: string;
  description: string;
  homepage: string;
  license: string;
  checksum: string;
  signed: boolean;
  enabled: boolean;
};

// ----- Phase A: Brand-poster templates, products, filters, render -----

export type AspectRatio = "1:1" | "4:5" | "9:16" | "16:9";

export type LayerType =
  | "ai_background"
  | "ai_image"
  | "product_cutout"
  | "text"
  | "image"
  | "shape"
  | "video_background";

export interface LayerConfigText {
  content: string;
  font_family?: string;
  font_size?: number;
  color?: string;
  background_color?: string;
  padding?: number;
  border_radius?: number;
  text_align?: "left" | "center" | "right";
  text_transform?: "none" | "uppercase" | "lowercase" | "capitalize";
  letter_spacing?: number;
  line_height?: number;
  font_weight?: "normal" | "bold" | "light";
  text_shadow?: {
    color: string;
    blur: number;
    offset_x: number;
    offset_y: number;
  };
}

export interface LayerConfigBackground {
  prompt: string;
  negative_prompt?: string;
  model?: string;
  seed?: number;
}

export interface LayerConfigProduct {
  slot?: "center" | "left" | "right" | "top" | "bottom" | "custom";
  auto_cutout?: boolean;
  shadow?: boolean;
  shadow_color?: string;
  shadow_blur?: number;
  shadow_offset_x?: number;
  shadow_offset_y?: number;
  max_width_percent?: number;
  max_height_percent?: number;
}

export interface LayerConfigImage {
  src?: string;
  object_fit?: "cover" | "contain" | "fill";
  border_radius?: number;
  border_width?: number;
  border_color?: string;
}

export interface LayerConfigShape {
  shape_type: "rectangle" | "circle" | "line";
  fill_color?: string;
  stroke_color?: string;
  stroke_width?: number;
}

export interface LayerConfigVideo {
  prompt: string;
  model: "fal_video" | "minimax_h3" | "comfyui";
  duration: number;
  loop: boolean;
}

export type LayerConfig =
  | LayerConfigBackground
  | LayerConfigProduct
  | LayerConfigText
  | LayerConfigImage
  | LayerConfigShape
  | LayerConfigVideo;

export interface TemplateLayer {
  id: string;
  type: LayerType;
  name: string;
  visible?: boolean;
  locked?: boolean;
  blend_mode?: "normal" | "multiply" | "screen" | "overlay" | "soft_light";
  opacity?: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  rotation?: number;
  config: LayerConfig;
}

export interface Template {
  id?: number | string;
  name: string;
  category?: string;
  aspect_ratio: AspectRatio;
  canvas: { width: number; height: number };
  safe_zones?: { top?: number; bottom?: number; left?: number; right?: number };
  layers: TemplateLayer[];
  brand_locks?: string[];
  default_filter?: string;
  ai_prompt_template?: string;
  preview_path?: string | null;
  is_builtin?: boolean;
  is_custom?: boolean;
  parent_template_id?: number | null;
  created_at?: number;
  brand_id?: number | null;
  canvas_w?: number;
  canvas_h?: number;
}

export interface Product {
  id: number;
  brand_id: number | null;
  name: string;
  price: number | null;
  category: string | null;
  collection: string | null;
  description: string | null;
  image_path: string | null;
  cutout_path: string | null;
  tags: string[];
  launch_date: string | null;
  created_at: number;
  updated_at: number;
}

export interface RenderResult {
  output_id: number;
  file_path: string;
  cost_usd: number;
  cached_background?: boolean;
  elapsed_seconds?: number;
  rel_url?: string | null;
}

export interface OutputRow {
  id: number;
  brand_id: number | null;
  product_id: number | null;
  template_id: number | null;
  type: string;
  file_path: string;
  aspect_ratio: string | null;
  filter_applied: string | null;
  status: string;
  cost_usd: number;
  created_at: number;
  rel_url?: string | null;
}

export interface FilterPreset {
  name: string;
  settings: Record<string, number>;
}

export interface UserFilterPreset {
  id: number;
  brand_id: number | null;
  name: string;
  settings: Record<string, number>;
}
