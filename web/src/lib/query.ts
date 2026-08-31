import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  Brand,
  Draft,
  Job,
  OutputItem,
  RefItem,
  RefTag,
} from "./types";

export const queryKeys = {
  health: ["health"] as const,
  keys: ["keys"] as const,
  refs: ["refs"] as const,
  brands: ["brands"] as const,
  drafts: ["drafts"] as const,
  jobs: ["jobs"] as const,
  job: (id: string) => ["jobs", id] as const,
  outputs: ["outputs"] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.health(),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

export function useKeys() {
  return useQuery({
    queryKey: queryKeys.keys,
    queryFn: () => api.listKeys().then((r) => r.keys),
  });
}

export function useSetKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ env_var, value }: { env_var: string; value: string }) =>
      api.setKey(env_var, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.keys }),
  });
}

export function useDeleteKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (env_var: string) => api.deleteKey(env_var),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.keys }),
  });
}

export type RefsData = { refs: RefItem[]; tags: RefTag[] };

export function useRefs() {
  return useQuery<RefsData>({
    queryKey: queryKeys.refs,
    queryFn: () => api.listRefs(),
  });
}

export function useUploadRef() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, tags }: { file: File; tags: string[] }) =>
      api.uploadRef(file, tags),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.refs }),
  });
}

export function useSetRefTags() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, tags }: { id: string; tags: string[] }) =>
      api.setRefTags(id, tags),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.refs }),
  });
}

export function useDeleteRef() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteRef(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.refs }),
  });
}

export type BrandsData = { brands: Brand[]; active: Brand | null };

export function useBrands() {
  return useQuery<BrandsData>({
    queryKey: queryKeys.brands,
    queryFn: () => api.listBrands(),
  });
}

export function useCreateBrand() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Brand>) => api.createBrand(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.brands }),
  });
}

export function useUpdateBrand() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Brand> }) =>
      api.updateBrand(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.brands }),
  });
}

export function useDeleteBrand() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteBrand(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.brands }),
  });
}

export function useActivateBrand() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.activateBrand(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.brands }),
  });
}

export function useClearActiveBrand() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.clearActiveBrand(),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.brands }),
  });
}

export type DraftsData = {
  drafts: Draft[];
  categories: { category: string; count: number }[];
};

export function useDrafts(params?: {
  query?: string;
  category?: string;
  favorites_only?: boolean;
}) {
  return useQuery<DraftsData>({
    queryKey: ["drafts", params ?? {}],
    queryFn: () => api.listDrafts(params),
  });
}

export function useCreateDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Draft>) => api.createDraft(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["drafts"] }),
  });
}

export function useDeleteDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteDraft(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["drafts"] }),
  });
}

export function useFavoriteDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.favoriteDraft(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["drafts"] }),
  });
}

export function useJobs() {
  return useQuery<Job[]>({
    queryKey: queryKeys.jobs,
    queryFn: () => api.listJobs().then((r) => r.jobs),
    refetchInterval: 5_000,
  });
}

export function useJob(id: string | null | undefined) {
  return useQuery<Job>({
    queryKey: id ? queryKeys.job(id) : ["jobs", "none"],
    queryFn: () => api.getJob(id!).then((r) => r.job),
    enabled: !!id,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (!status) return 2_000;
      if (status === "succeeded" || status === "failed" || status === "cancelled")
        return false;
      return 2_000;
    },
  });
}

export function useGenerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.generate>[0]) => api.generate(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.jobs });
    },
  });
}

export function useOutputs() {
  return useQuery<OutputItem[]>({
    queryKey: queryKeys.outputs,
    queryFn: () => api.listOutputs().then((r) => r.outputs),
  });
}
