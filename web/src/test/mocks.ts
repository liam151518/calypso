// Shared mock data + a vi.mock helper for query hooks.
import { vi } from "vitest";
import type {
  Brand,
  Draft,
  Job,
  KeyStatus,
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
  };
}
