import { cn } from "@/lib/cn";

export function Pill({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "ok" | "warn" | "error" | "info" | "neutral";
}) {
  const toneClass = {
    ok: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    warn: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    error: "bg-rose-500/15 text-rose-300 border-rose-500/30",
    info: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
    neutral: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
  }[tone];

  return <span className={cn("pill border", toneClass)}>{children}</span>;
}
