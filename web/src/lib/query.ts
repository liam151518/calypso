import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  Brand,
  CostEstimate,
  Draft,
  ImageJob,
  Job,
  ModelSpec,
  NodeSchemaResponse,
  OutputItem,
  Pipeline,
  PipelineRun,
  RefItem,
  RefTag,
} from "./types";
import type { ImageOutputItem } from "./api";

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

export type ModelsData = {
  models: ModelSpec[];
  defaults: { video: string; image: string };
};

export function useModels() {
  return useQuery<ModelsData>({
    queryKey: ["models"],
    queryFn: () => api.listModels(),
    staleTime: 60_000,
  });
}

export function useEstimateCost() {
  return useMutation<CostEstimate, Error, Parameters<typeof api.estimateCost>[0]>({
    mutationFn: (data) => api.estimateCost(data).then((r) => r.estimate),
  });
}

export function useImageJobs() {
  return useQuery<ImageJob[]>({
    queryKey: ["image-jobs"],
    queryFn: () => api.listImageJobs().then((r) => r.jobs),
    refetchInterval: 5_000,
  });
}

export function useImageJob(id: string | null | undefined) {
  return useQuery<ImageJob>({
    queryKey: id ? ["image-jobs", id] : ["image-jobs", "none"],
    queryFn: () => api.getImageJob(id!).then((r) => r.job),
    enabled: !!id,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (!status) return 2_000;
      if (status === "succeeded" || status === "failed") return false;
      return 2_000;
    },
  });
}

export function useGenerateImage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.generateImage>[0]) =>
      api.generateImage(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["image-jobs"] });
      qc.invalidateQueries({ queryKey: queryKeys.outputs });
      qc.invalidateQueries({ queryKey: ["image-outputs"] });
    },
  });
}

export function useImageOutputs() {
  return useQuery<ImageOutputItem[]>({
    queryKey: ["image-outputs"],
    queryFn: () => api.listImageOutputs().then((r) => r.outputs),
  });
}

// ----- Phase A: pipelines -----

export function useNodeSchemas() {
  return useQuery<NodeSchemaResponse>({
    queryKey: ["pipeline-node-schemas"],
    queryFn: () => api.listNodeSchemas().then((r) => {
      const { ok, ...rest } = r as { ok: boolean } & NodeSchemaResponse;
      void ok;
      return rest;
    }),
    staleTime: Infinity,
  });
}

export function usePipelines() {
  return useQuery<Pipeline[]>({
    queryKey: ["pipelines"],
    queryFn: () => api.listPipelines().then((r) => r.pipelines),
  });
}

export function usePipeline(id: number | null) {
  return useQuery<Pipeline | null>({
    queryKey: ["pipeline", id],
    enabled: id != null,
    queryFn: () =>
      id == null
        ? Promise.resolve(null)
        : api.getPipeline(id).then((r) => r.pipeline),
  });
}

export function useCreatePipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.createPipeline>[0]) =>
      api.createPipeline(data).then((r) => r.pipeline),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipelines"] });
    },
  });
}

export function useUpdatePipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Parameters<typeof api.updatePipeline>[1];
    }) => api.updatePipeline(id, data).then((r) => r.pipeline),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["pipeline", p.id] });
    },
  });
}

export function useDeletePipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deletePipeline(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipelines"] });
    },
  });
}

export function useRunPipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, triggered_by }: { id: number; triggered_by?: string }) =>
      api.runPipeline(id, triggered_by).then((r) => r.run),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: ["pipeline-runs", run.pipeline_id] });
    },
  });
}

export function usePipelineRuns(pipelineId: number | null) {
  return useQuery<PipelineRun[]>({
    queryKey: ["pipeline-runs", pipelineId],
    enabled: pipelineId != null,
    refetchInterval: 2000,
    queryFn: () =>
      pipelineId == null
        ? Promise.resolve([])
        : api.listPipelineRuns(pipelineId).then((r) => r.runs),
  });
}

export function usePipelineRun(runId: number | null) {
  return useQuery<PipelineRun | null>({
    queryKey: ["pipeline-run", runId],
    enabled: runId != null,
    refetchInterval: 1500,
    queryFn: () =>
      runId == null
        ? Promise.resolve(null)
        : api.getPipelineRun(runId).then((r) => r.run),
  });
}

export function useExtensions() {
  return useQuery<import("./types").Extension[]>({
    queryKey: ["extensions"],
    queryFn: () => api.listExtensions().then((r) => r.extensions),
  });
}

export function useToggleExtension() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enable }: { id: string; enable: boolean }) =>
      enable ? api.enableExtension(id) : api.disableExtension(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["extensions"] }),
  });
}
