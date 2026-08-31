import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/Card";
import { Pill } from "@/components/Pill";

export const dynamic = "force-dynamic";

export default async function WorkflowsPage() {
  const workflows = await api.workflows();
  if (!workflows) return <Offline />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold glow">Workflows</h1>
      <p className="text-sm text-zinc-400">n8n and ComfyUI workflow JSON exports.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {workflows.map((w) => (
          <Card key={w.path}>
            <CardHeader>
              <CardTitle className="font-mono text-xs">{w.name}</CardTitle>
            </CardHeader>
            <CardBody>
              <div className="text-[10px] text-zinc-500 font-mono mb-2">{w.path}</div>
              <div className="flex items-center gap-2 mb-2">
                <Pill tone="info">{w.nodes} nodes</Pill>
                {w.triggers.map((t) => (
                  <Pill key={t} tone="neutral">{t}</Pill>
                ))}
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Offline() {
  return (
    <Card>
      <CardBody>
        <div className="text-brand font-semibold">Backend offline.</div>
      </CardBody>
    </Card>
  );
}
