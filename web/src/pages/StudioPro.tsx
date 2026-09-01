import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { studioPro } from "@/lib/api";
import { BriefInput } from "@/components/studio_pro/BriefInput";
import { SuggestionGrid } from "@/components/studio_pro/SuggestionGrid";
import { AgentLog, AgentLogEntry } from "@/components/studio_pro/AgentLog";

interface StudioSuggestion {
  id?: number;
  template_id: number | null;
  layer_overrides: Record<string, unknown>;
  rationale: string;
  platforms: string[];
  duration_s?: number | null;
  cost_usd: number;
  confidence_score: number;
}

interface StudioResponse {
  run_id: string;
  suggestions: StudioSuggestion[];
  agent_log: AgentLogEntry[];
  spent_usd: number;
}

export function StudioPro() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [runId, setRunId] = useState<string | null>(null);

  const generate = useMutation({
    mutationFn: (brief: Parameters<typeof BriefInput>[0]["onSubmit"] extends (b: infer B) => void ? B : never) =>
      studioPro.generate(brief),
    onSuccess: (data: StudioResponse) => setRunId(data.run_id),
  });

  // Once we have a run_id, fetch the persisted suggestion rows so we get
  // their `id` (needed for accept / schedule).
  const persisted = useQuery({
    queryKey: ["studio-pro-log", runId],
    queryFn: () => studioPro.log(runId!),
    enabled: !!runId,
  });

  const accept = useMutation({
    mutationFn: (s: StudioSuggestion & { id?: number }) =>
      studioPro.accept(s.id ?? 0, {
        product_id: null,
        brand_id: null,
      }),
    onSuccess: (data: { editor_url: string }) => navigate(data.editor_url),
  });

  const schedule = useMutation({
    mutationFn: (s: StudioSuggestion & { id?: number }) =>
      studioPro.schedule(s.id ?? 0, {
        run_at: Math.floor(Date.now() / 1000) + 3600,
        platform: s.platforms?.[0] ?? "instagram",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["studio-pro-log", runId] }),
  });

  // Merge local suggestions (with rationale/cost/confidence) + persisted ids.
  const suggestions: StudioSuggestion[] = (() => {
    const persistedRows = (persisted.data?.suggestions ?? []) as Array<
      StudioSuggestion & { id: number }
    >;
    return (generate.data?.suggestions ?? []).map((s, idx) => ({
      ...s,
      id: persistedRows[idx]?.id,
    }));
  })();

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Studio Pro</h1>
        <p className="text-sm text-slate-500">
          Brand-poster multi-agent generator. Type a brief, get three
          pre-scored suggestions, then edit or schedule your favorite.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-1">
          <BriefInput onSubmit={(b) => generate.mutate(b)} isLoading={generate.isPending} />
        </div>
        <div className="md:col-span-2 space-y-4">
          <SuggestionGrid
            suggestions={suggestions}
            previews={{}}
            onAccept={(s) => accept.mutate(s)}
            onSchedule={(s) => schedule.mutate(s)}
            onReject={() => {
              /* No-op for now; suggestions stay until a new run. */
            }}
            busy={accept.isPending || schedule.isPending}
          />
          {generate?.data?.agent_log && (
            <AgentLog entries={generate.data.agent_log} />
          )}
          {generate.isError && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              Failed to generate suggestions. Please try a different brief.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default StudioPro;