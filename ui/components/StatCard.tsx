import { cn } from "@/lib/cn";

export function StatCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  tone?: "ok" | "warn" | "error" | "neutral";
}) {
  const toneClass = {
    ok: "text-emerald-400",
    warn: "text-amber-400",
    error: "text-rose-400",
    neutral: "text-zinc-100",
  }[tone];

  return (
    <div className="card p-4">
      <div className="text-[10px] uppercase tracking-widest text-zinc-500">{label}</div>
      <div className={cn("mt-1 text-xl font-semibold", toneClass)}>{value}</div>
    </div>
  );
}
