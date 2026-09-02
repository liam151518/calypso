// Shared mock data + a vi.mock helper for query hooks.
import { vi } from "vitest";
import type {
  Brand,
  CostEstimate,
  Draft,
  FilterPreset,
  ImageJob,
  Job,
  KeyStatus,
  ModelSpec,
  OutputItem,
  RefItem,
  RefTag,
  Template,
} from "@/lib/types";

export const MOCK_REFS: RefItem[] = [
  {
    id: "ref_01.png",
    name: "ref_01.png",
    ext: "png",
    size_kb: 1.5,
    rel_url: "/references/file/ref_01.png",
    tags: ["character", "hero"],
  },
  {
    id: "ref_02.png",
    name: "ref_02.png",
    ext: "png",
    size_kb: 1.4,
    rel_url: "/references/file/ref_02.png",
    tags: ["background"],
  },
];

export const MOCK_TAGS: RefTag[] = [
  { name: "character", count: 1 },
  { name: "background", count: 1 },
  { name: "hero", count: 1 },
];

export const MOCK_BRAND: Brand = {
  id: 1,
  name: "Gachakingdoms",
  tagline: "Pull the blade.",
  audience: "Collectors",
  palette: ["#ff6a1f", "#0a0a0c", "#f6efe6"],
  typography: "Cormorant",
  voice: "cinematic",
  do_examples: "tight close-ups",
  dont_examples: "stock typography",
  style_guide: "Hero always off-axis.",
  created_at: 0,
  updated_at: 0,
};

export const MOCK_DRAFTS: Draft[] = [
  {
    id: 1,
    name: "Damascus reveal",
    body: "Damascus cabinet reveal, golden hour, slow dolly.",
    category: "hero",
    is_favorite: false,
    created_at: 0,
    updated_at: 0,
  },
  {
    id: 2,
    name: "Forge hands",
    body: "Close-up on hands shaping a blade. Sparks.",
    category: "craft",
    is_favorite: true,
    created_at: 0,
    updated_at: 0,
  },
];

export const MOCK_JOBS: Job[] = [
  {
    id: "job-1",
    status: "succeeded",
    prompt: "Hero draws blade",
    effective_prompt: "Hero draws blade",
    model: "auto",
    duration: 8,
    resolution: "768p",
    reference: null,
    references: null,
    ref_ids: [],
    draft_id: null,
    brand_id: null,
    batch_id: null,
    output_rel: "/outputs/job-1/video.mp4",
    elapsed_seconds: 1,
    cost_usd: 0.01,
    error: null,
  },
];

export const MOCK_OUTPUTS: OutputItem[] = [
  {
    id: "job-1",
    rel_url: "/outputs/job-1/video.mp4",
    size_mb: 1.2,
    created: Date.now() / 1000 - 60,
    prompt: "Hero draws blade",
    brand_name: "Gachakingdoms",
    draft_name: null,
    refs: [],
  },
];

export const MOCK_KEYS: KeyStatus[] = [
  {
    env_var: "FAL_API_KEY",
    service: "fal.ai",
    placeholder: "fal-xxx",
    group: "Generation",
    required: true,
    docs_url: "https://fal.ai/dashboard/keys",
    description: "Primary cloud provider.",
    is_set: true,
    masked: "•••••abcd",
    is_custom: false,
  },
];

export const MOCK_MODELS: ModelSpec[] = [
  {
    id: "minimax/h3",
    name: "MiniMax H3",
    category: "video",
    vendor: "MiniMax",
    description: "Reference-driven cinematic video.",
    durations: [4, 6, 8, 10, 12],
    resolutions: ["480p", "768p", "1080p"],
    aspect_ratios: [],
    per_second_usd: { "480p": 0.025, "768p": 0.045, "1080p": 0.075 },
    per_image_usd: 0,
    badge: "default",
    is_default: true,
  },
  {
    id: "kling-video/v2.6/pro",
    name: "Kling 2.6 Pro",
    category: "video",
    vendor: "Kuaishou",
    description: "Strong motion.",
    durations: [5, 10],
    resolutions: ["480p", "768p", "1080p"],
    aspect_ratios: [],
    per_second_usd: { "480p": 0.05, "768p": 0.07, "1080p": 0.10 },
    per_image_usd: 0,
    badge: "",
    is_default: false,
  },
  {
    id: "flux-pro/v1.1",
    name: "Flux Pro 1.1",
    category: "image",
    vendor: "Black Forest Labs",
    description: "Photorealistic product imagery.",
    durations: [],
    resolutions: [],
    aspect_ratios: ["1:1", "16:9", "9:16", "4:3", "3:4"],
    per_second_usd: {},
    per_image_usd: 0.05,
    badge: "default",
    is_default: true,
  },
];

export const MOCK_ESTIMATE_VIDEO: CostEstimate = {
  usd: 0.36,
  model_id: "minimax/h3",
  category: "video",
  duration: 8,
  resolution: "768p",
};

export const MOCK_ESTIMATE_IMAGE: CostEstimate = {
  usd: 0.05,
  model_id: "flux-pro/v1.1",
  category: "image",
  aspect_ratio: "1:1",
  num_images: 1,
};

export const MOCK_IMAGE_JOBS: ImageJob[] = [
  {
    job_id: "img-1",
    status: "succeeded",
    prompt: "A samurai helmet",
    model: "flux-pro/v1.1",
    aspect_ratio: "1:1",
    num_images: 1,
    ref_ids: [],
    brand_id: null,
    draft_id: null,
    output_paths: ["/outputs/img-1/image-1.png"],
    output_rel: "/outputs/file/img-1/image-1.png",
    cost_usd: 0.05,
    elapsed_seconds: 2.4,
    error: null,
    created_at: Date.now() / 1000 - 60,
    updated_at: Date.now() / 1000 - 50,
  },
];

// ----- Phase B: editor + brand-poster mock data -----

export const MOCK_TEMPLATES: Template[] = [
  {
    id: 1,
    name: "Minimal Launch",
    category: "launch",
    aspect_ratio: "1:1",
    canvas: { width: 1080, height: 1080 },
    safe_zones: { top: 5, bottom: 5, left: 5, right: 5 },
    layers: [
      {
        id: "bg-1",
        type: "ai_background",
        name: "Background",
        x: 0,
        y: 0,
        width: 100,
        height: 100,
        config: { prompt: "soft gradient backdrop" } as Template["layers"][number]["config"],
      },
      {
        id: "title-1",
        type: "text",
        name: "Title",
        x: 10,
        y: 35,
        width: 80,
        height: 15,
        config: {
          content: "NOW LIVE",
          color: "#111111",
          font_size: 64,
          font_family: "sans-serif",
          text_align: "center",
        } as Template["layers"][number]["config"],
      },
      {
        id: "product-1",
        type: "product_cutout",
        name: "Product",
        x: 25,
        y: 50,
        width: 50,
        height: 35,
        config: { slot: "center", shadow: true } as Template["layers"][number]["config"],
      },
    ],
    brand_locks: ["palette"],
    default_filter: "moody",
    is_builtin: true,
    is_custom: false,
  },
  {
    id: 2,
    name: "Bold Drop",
    category: "launch",
    aspect_ratio: "4:5",
    canvas: { width: 1080, height: 1350 },
    layers: [
      {
        id: "shape-1",
        type: "shape",
        name: "Accent bar",
        x: 0,
        y: 0,
        width: 100,
        height: 8,
        config: { shape_type: "rectangle", fill_color: "#0a0a0c" } as Template["layers"][number]["config"],
      },
    ],
    is_builtin: true,
    is_custom: false,
  },
];

export const MOCK_FILTERS: FilterPreset[] = [
  { name: "moody", settings: { brightness: -0.2, contrast: 0.15, saturation: -0.1 } },
  { name: "bright", settings: { brightness: 0.15, contrast: 0.05, saturation: 0.1 } },
  { name: "vintage", settings: { brightness: -0.05, contrast: 0.1, saturation: -0.3 } },
  { name: "minimal", settings: { brightness: 0.0, contrast: 0.0, saturation: -0.5 } },
  { name: "neon", settings: { brightness: 0.0, contrast: 0.2, saturation: 0.4 } },
];

/**
 * Build a query-hook mock factory you can spread into a `vi.mock("@/lib/query", ...)`.
 * Each hook returns a stable shape so React components render predictably.
 */
export function buildQueryMock() {
  return {
    useHealth: () => ({ data: { status: "ok", service: "calypso", version: "0.1.0" } }),
    useRefs: () => ({ data: { refs: MOCK_REFS, tags: MOCK_TAGS }, isLoading: false }),
    useBrands: () => ({ data: { brands: [MOCK_BRAND], active: MOCK_BRAND }, isLoading: false }),
    useDrafts: () => ({
      data: {
        drafts: MOCK_DRAFTS,
        categories: [
          { category: "hero", count: 1 },
          { category: "craft", count: 1 },
        ],
      },
      isLoading: false,
    }),
    useJobs: () => ({ data: MOCK_JOBS, isLoading: false }),
    useJob: () => ({ data: MOCK_JOBS[0], isLoading: false }),
    useOutputs: () => ({ data: MOCK_OUTPUTS, isLoading: false }),
    useKeys: () => ({
      data: {
        keys: MOCK_KEYS,
        custom: [],
        groups: [{ name: "Generation", keys: MOCK_KEYS.map((k) => k.env_var) }],
      },
      isLoading: false,
    }),
    useGenerate: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useClearActiveBrand: () => ({ mutate: vi.fn(), isPending: false }),
    useActivateBrand: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteBrand: () => ({ mutate: vi.fn(), isPending: false }),
    useCreateBrand: () => ({ mutate: vi.fn(), isPending: false }),
    useUpdateBrand: () => ({ mutate: vi.fn(), isPending: false }),
    useCreateDraft: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteDraft: () => ({ mutate: vi.fn(), isPending: false }),
    useFavoriteDraft: () => ({ mutate: vi.fn(), isPending: false }),
    useUploadRef: () => ({ mutate: vi.fn(), isPending: false }),
    useSetRefTags: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteRef: () => ({ mutate: vi.fn(), isPending: false }),
    useSetKey: () => ({ mutate: vi.fn(), isPending: false }),
    useDeleteKey: () => ({ mutate: vi.fn(), isPending: false }),
    useModels: () => ({
      data: { models: MOCK_MODELS, defaults: { video: "minimax/h3", image: "flux-pro/v1.1" } },
      isLoading: false,
    }),
    useEstimateCost: () => ({ mutate: vi.fn(), data: null, isPending: false }),
    useImageJobs: () => ({ data: MOCK_IMAGE_JOBS, isLoading: false }),
    useImageJob: () => ({ data: MOCK_IMAGE_JOBS[0], isLoading: false }),
    useGenerateImage: () => ({ mutate: vi.fn(), isPending: false }),
    useImageOutputs: () => ({ data: [], isLoading: false }),
    // ----- Phase B: editor + brand-poster hooks -----
    useTemplates: () => ({ data: { templates: MOCK_TEMPLATES, aspect_ratios: ["1:1","4:5","9:16","16:9"], layer_types: ["text","image","shape"] }, isLoading: false }),
    useTemplate: () => ({ data: MOCK_TEMPLATES[0], isLoading: false }),
    useCreateTemplate: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useUpdateTemplate: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useDeleteTemplate: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useDuplicateTemplate: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useBootBuiltins: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useProducts: () => ({ data: { products: [] }, isLoading: false }),
    useProduct: () => ({ data: null, isLoading: false }),
    useCreateProduct: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useDeleteProduct: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useImportProducts: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useCutout: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useFilters: () => ({ data: { presets: MOCK_FILTERS, user: [] }, isLoading: false }),
    useRender: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
    useRenderBatch: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
  };
}
