import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { phaseG, Preset, AutomationRule } from "@/lib/api";

export type { Preset, AutomationRule };

export interface CreatePresetInput {
  brand_id: number | null;
  name: string;
  description?: string | null;
  template_id?: number | null;
  filter?: string | null;
  product_filter?: Record<string, unknown>;
}

export function usePresets(brandId?: number | null) {
  return useQuery({
    queryKey: ["presets", brandId ?? null],
    queryFn: () => phaseG.listPresets(brandId),
  });
}

export function useCreatePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreatePresetInput) => phaseG.createPreset(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["presets"] }),
  });
}

export function useDeletePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => phaseG.deletePreset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["presets"] }),
  });
}

export function useApplyPreset() {
  return useMutation({
    mutationFn: (args: { preset_id: number; product_ids: number[] }) =>
      phaseG.applyPreset(args.preset_id, args.product_ids),
  });
}

export function useAutomationRules(brandId?: number | null) {
  return useQuery({
    queryKey: ["automation", brandId ?? null],
    queryFn: () => phaseG.listAutomationRules(brandId),
  });
}

export function useCreateAutomationRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      brand_id: number | null;
      name: string;
      trigger: string;
      conditions: AutomationRule["conditions"];
      action: AutomationRule["action"];
      is_active?: boolean;
    }) => phaseG.createAutomationRule(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automation"] }),
  });
}

export function useToggleAutomationRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { rule_id: number; is_active: boolean }) =>
      phaseG.toggleAutomationRule(args.rule_id, args.is_active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automation"] }),
  });
}

export function useDeleteAutomationRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => phaseG.deleteAutomationRule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automation"] }),
  });
}