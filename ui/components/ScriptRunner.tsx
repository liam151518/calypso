"use client";

import { useState } from "react";
import { Play, Loader2 } from "lucide-react";
import { api, type ScriptRunResult } from "@/lib/api";
import { Pill } from "./Pill";

export function ScriptRunner({ name }: { name: string }) {
  const [args, setArgs] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ScriptRunResult | null>(null);

  async function run() {
    setBusy(true);
    setResult(null);
    const parsed = args.trim() ? args.trim().split(/\s+/) : [];
    const res = await api.scriptRun(name, parsed);
    setResult(res ?? { ok: false, exit_code: -1, stdout: "", stderr: "backend offline", duration_ms: 0 });
    setBusy(false);
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          value={args}
          onChange={(e) => setArgs(e.target.value)}
          placeholder="--help or arg1 arg2…"
          className="flex-1 bg-black/30 border border-brand-border rounded px-2 py-1 text-xs font-mono"
        />
        <button
          onClick={run}
          disabled={busy}
          className="flex items-center gap-1 bg-brand/15 hover:bg-brand/25 border border-brand/30 text-brand rounded px-3 py-1 text-xs disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          Run
        </button>
      </div>
      {result && (
        <div className="bg-black/40 border border-brand-border rounded p-2 text-[11px] font-mono">
          <div className="flex items-center gap-2 mb-1">
            <Pill tone={result.ok ? "ok" : "error"}>
              {result.ok ? "ok" : `exit ${result.exit_code}`}
            </Pill>
            <span className="text-zinc-500">{result.duration_ms}ms</span>
          </div>
          {result.stdout && (
            <pre className="whitespace-pre-wrap text-zinc-300 max-h-40 overflow-auto">{result.stdout}</pre>
          )}
          {result.stderr && (
            <pre className="whitespace-pre-wrap text-rose-300 max-h-40 overflow-auto">{result.stderr}</pre>
          )}
        </div>
      )}
    </div>
  );
}
