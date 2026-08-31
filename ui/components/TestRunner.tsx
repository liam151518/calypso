"use client";

import { useState } from "react";
import { FlaskConical, Loader2 } from "lucide-react";
import { api, type TestRunResult } from "@/lib/api";
import { Pill } from "./Pill";

export function TestRunner() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TestRunResult | null>(null);

  async function run() {
    setBusy(true);
    setResult(null);
    const res = await api.testsRun();
    setResult(res ?? { ok: false, duration_ms: 0, passed: 0, failed: 0, output_tail: "backend offline" });
    setBusy(false);
  }

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold">Run pytest</div>
        <button
          onClick={run}
          disabled={busy}
          className="flex items-center gap-2 bg-brand/15 hover:bg-brand/25 border border-brand/30 text-brand rounded px-3 py-1 text-xs disabled:opacity-50"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <FlaskConical size={12} />}
          {busy ? "Running…" : "Run all tests"}
        </button>
      </div>
      {result && (
        <div className="bg-black/40 border border-brand-border rounded p-3 text-[11px] font-mono">
          <div className="flex items-center gap-2 mb-2">
            <Pill tone={result.ok ? "ok" : "error"}>{result.ok ? "ok" : "failed"}</Pill>
            <span className="text-zinc-500">{result.duration_ms}ms</span>
            <Pill tone="info">{result.passed} pass</Pill>
            {result.failed > 0 && <Pill tone="error">{result.failed} fail</Pill>}
          </div>
          <pre className="whitespace-pre-wrap text-zinc-300 max-h-60 overflow-auto">{result.output_tail}</pre>
        </div>
      )}
    </div>
  );
}
