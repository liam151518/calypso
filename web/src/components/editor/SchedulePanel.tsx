import { useState } from "react";
import { useEditorStore } from "@/hooks/useEditor";
import { useSchedule, useSchedulerJobs } from "@/hooks/contentFlow";

const PLATFORMS = ["instagram", "tiktok", "x", "linkedin", "facebook"];

export function SchedulePanel() {
  const template = useEditorStore((s) => s.template);
  const product = useEditorStore((s) => s.product);
  const brand = useEditorStore((s) => s.brand);

  const schedule = useSchedule();
  const jobsQuery = useSchedulerJobs("queued");
  const [platform, setPlatform] = useState<string>("instagram");
  const [whenIso, setWhenIso] = useState<string>(() => {
    const t = new Date();
    t.setDate(t.getDate() + 1);
    t.setHours(9, 0, 0, 0);
    // toISOString gives "2026-09-02T07:00:00.000Z" — convert to local-naive
    // for the <input type="datetime-local"> control.
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}T${pad(t.getHours())}:${pad(t.getMinutes())}`;
  });

  const onSchedule = () => {
    if (!template?.id || !product?.id) return;
    const runAt = new Date(whenIso).getTime() / 1000;
    schedule.mutate({
      name: `Publish ${product.name ?? "output"} on ${platform}`,
      kind: "publish_output",
      run_at: runAt,
      payload: {
        output_id: 0, // bound when the current draft is rendered
        product_id: product.id,
        template_id: template.id,
        brand_id: brand?.id ?? null,
        platform,
      },
    });
  };

  const jobs = jobsQuery.data?.jobs ?? [];

  return (
    <section className="flex flex-col gap-y-2 border-t bg-stone-50 px-3 py-2 text-xs">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-stone-700">Scheduler</h3>
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="h-7 rounded border px-2 text-xs"
          aria-label="Schedule platform"
        >
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </header>

      <div className="grid grid-cols-2 items-center gap-2">
        <input
          type="datetime-local"
          value={whenIso}
          onChange={(e) => setWhenIso(e.target.value)}
          className="h-7 rounded border px-2 text-xs"
        />
        <button
          onClick={onSchedule}
          disabled={!template?.id || !product?.id || schedule.isPending}
          className="rounded border bg-white px-2 py-1 hover:bg-stone-50 disabled:opacity-50"
          data-testid="schedule-output"
        >
          {schedule.isPending ? "Scheduling…" : "Schedule"}
        </button>
      </div>

      <div className="text-[11px] text-muted-foreground">
        {jobs.length} queued job{jobs.length === 1 ? "" : "s"}
      </div>
    </section>
  );
}