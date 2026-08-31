import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/Card";
import { Pill } from "@/components/Pill";

export const dynamic = "force-dynamic";

const STATUS_TONE: Record<string, "ok" | "warn" | "info"> = {
  done: "ok",
  in_progress: "warn",
  pending: "info",
};

export default async function PhasesPage() {
  const phases = await api.phases();
  if (!phases) return <OfflineNote />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold glow">Phases</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {phases.map((p) => (
          <Card key={p.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{p.name}</CardTitle>
                <Pill tone={STATUS_TONE[p.status]}>{p.status.replace("_", " ")}</Pill>
              </div>
            </CardHeader>
            <CardBody>
              <p className="text-sm text-zinc-300 mb-3">{p.summary}</p>
              <ul className="space-y-1">
                {p.deliverables.map((d) => (
                  <li key={d} className="text-xs text-zinc-400 flex items-start gap-2">
                    <span className="text-brand">▸</span> {d}
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}

function OfflineNote() {
  return (
    <Card>
      <CardBody>
        <div className="text-brand font-semibold">Backend offline.</div>
        <div className="text-sm text-zinc-400">Run <code>npm run dev:all</code> from <code>ui/</code>.</div>
      </CardBody>
    </Card>
  );
}
