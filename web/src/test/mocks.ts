// Shared mock data + a vi.mock helper for query hooks.
import { vi } from "vitest";
import type {
  Brand,
  CostEstimate,
  Draft,
  ImageJob,
  Job,
  KeyStatus,
  ModelSpec,
  OutputItem,
  RefItem,
  RefTag,
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
    is_set: true,
    masked: "•••••abcd",
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
    useKeys: () => ({ data: MOCK_KEYS, isLoading: false }),
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
  };
}
