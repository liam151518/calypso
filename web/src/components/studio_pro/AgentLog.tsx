import { ChevronDown, ChevronRight, Cpu } from "lucide-react";
import { useState } from "react";

export interface AgentLogEntry {
  agent: string;
  started_at?: number;
  finished_at?: number;
  status: "running" | "ok" | "error";
  outputs?: string[];
  note?: string;
  error?: string;
}

export interface AgentLogProps {
  entries: AgentLogEntry[];
}

export function AgentLog({ entries }: AgentLogProps) {
  const [open, setOpen] = useState(false);
  if (!entries.length) return null;
  return (
    <div className="rounded-md border border-slate-200 bg-white">
      <button
        onClick={() => setOpen((cur) => !cur)}
        className="flex w-full items-center justify-between p-3 text-left text-sm font-medium"
      >
        <span className="flex items-center gap-2">
          <Cpu className="h-4 w-4" />
          Agent log ({entries.length})
        </span>
        {open ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </button>
      {open && (
        <ul className="divide-y divide-slate-100">
          {entries.map((e, idx) => (
            <li key={`${e.agent}-${idx}`} className="p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">{e.agent}</span>
                <span
                  className={`text-xs uppercase ${
                    e.status === "ok"
                      ? "text-green-600"
                      : e.status === "error"
                      ? "text-red-600"
                      : "text-amber-600"
                  }`}
                >
                  {e.status}
                </span>
              </div>
              {e.note && (
                <p className="mt-1 text-xs text-slate-500">{e.note}</p>
              )}
              {e.error && (
                <p className="mt-1 text-xs text-red-500">{e.error}</p>
              )}
              {e.outputs && e.outputs.length > 0 && (
                <p className="mt-1 text-xs text-slate-400">
                  outputs: {e.outputs.join(", ")}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default AgentLog;