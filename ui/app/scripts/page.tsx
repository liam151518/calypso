import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/Card";
import { Pill } from "@/components/Pill";
import { ScriptRunner } from "@/components/ScriptRunner";

export const dynamic = "force-dynamic";

export default async function ScriptsPage() {
  const scripts = await api.scripts();
  if (!scripts) {
    return (
      <Card>
        <CardBody>
          <div className="text-brand font-semibold">Backend offline.</div>
          <div className="text-sm text-zinc-400">Run <code>npm run dev:all</code> from <code>ui/</code>.</div>
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold glow">Scripts</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {scripts.map((s) => (
          <Card key={s.name}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="font-mono text-xs">{s.name}</CardTitle>
                {s.has_cli && <Pill tone="info">CLI</Pill>}
              </div>
            </CardHeader>
            <CardBody>
              <p className="text-sm text-zinc-300 mb-3">{s.description}</p>
              <div className="text-[10px] text-zinc-500 font-mono mb-3">{s.path}</div>
              <ScriptRunner name={s.name} />
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
