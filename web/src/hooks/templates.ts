import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { brandPoster } from "@/lib/api";
import type { Template, RenderResult, FilterPreset, UserFilterPreset, Product, OutputRow } from "@/lib/types";

export const brandPosterQueryKeys = {
  templates: ["templates"] as const,
  template: (id: number) => ["templates", id] as const,
  products: ["products"] as const,
  product: (id: number) => ["products", id] as const,
  filters: ["filters"] as const,
  outputs: ["outputs", "images"] as const,
};

// ----- Templates -----

export function useTemplates(params?: { brand_id?: number; category?: string }) {
  return useQuery({
    queryKey: [...brandPosterQueryKeys.templates, params ?? {}],
    queryFn: () => brandPoster.listTemplates(params),
  });
}

export function useTemplate(id: number | null | undefined) {
  return useQuery({
    queryKey: id ? brandPosterQueryKeys.template(id) : ["templates", "none"],
    queryFn: () => brandPoster.getTemplate(id!).then((r) => r.template),
    enabled: !!id,
  });
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Template>) => brandPoster.createTemplate(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandPosterQueryKeys.templates }),
  });
}

export function useUpdateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data, force }: { id: number; data: Partial<Template>; force?: boolean }) =>
      brandPoster.updateTemplate(id, data, !!force),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: brandPosterQueryKeys.templates });
      qc.invalidateQueries({ queryKey: brandPosterQueryKeys.template(vars.id) });
    },
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, force }: { id: number; force?: boolean }) =>
      brandPoster.deleteTemplate(id, !!force),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandPosterQueryKeys.templates }),
  });
}

export function useDuplicateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      brandPoster.duplicateTemplate(id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandPosterQueryKeys.templates }),
  });
}

export function useBootBuiltins() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => brandPoster.bootBuiltins(),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandPosterQueryKeys.templates }),
  });
}

// ----- Products -----

export function useProducts(params?: { brand_id?: number; category?: string }) {
  return useQuery({
    queryKey: [...brandPosterQueryKeys.products, params ?? {}],
    queryFn: () => brandPoster.listProducts(params),
  });
}

export function useProduct(id: number | null | undefined) {
  return useQuery({
    queryKey: id ? brandPosterQueryKeys.product(id) : ["products", "none"],
    queryFn: () => brandPoster.getProduct(id!),
    enabled: !!id,
  });
}

export function useCreateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Product>) => brandPoster.createProduct(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandPosterQueryKeys.products }),
  });
}

export function useDeleteProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => brandPoster.deleteProduct(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandPosterQueryKeys.products }),
  });
}

export function useImportProducts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { brand_id?: number; rows?: unknown[]; csv?: string }) =>
      brandPoster.importProducts(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandPosterQueryKeys.products }),
  });
}

export function useCutout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, regenerate }: { id: number; regenerate?: boolean }) =>
      brandPoster.requestCutout(id, !!regenerate),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: brandPosterQueryKeys.product(vars.id) });
    },
  });
}

// ----- Filters -----

export type FiltersData = { presets: FilterPreset[]; user: UserFilterPreset[] };

export function useFilters() {
  return useQuery({
    queryKey: brandPosterQueryKeys.filters,
    queryFn: () => brandPoster.listFilters(),
  });
}

// ----- Render -----

export function useRender() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof brandPoster.render>[0]) => brandPoster.render(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandPosterQueryKeys.outputs }),
  });
}

export function useRenderBatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof brandPoster.renderBatch>[0]) => brandPoster.renderBatch(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: brandPosterQueryKeys.outputs }),
  });
}

export function useImageOutputs() {
  return useQuery<OutputRow[]>({
    queryKey: brandPosterQueryKeys.outputs,
    queryFn: () => brandPoster.listImageOutputs().then((r) => r.outputs),
    refetchInterval: 5_000,
  });
}

export type { Template, RenderResult, Product, OutputRow };