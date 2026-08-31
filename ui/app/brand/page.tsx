import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/Card";

export const dynamic = "force-dynamic";

export default async function BrandPage() {
  const files = await api.brandPack();
  if (!files) return <Offline />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold glow">Brand Pack</h1>
      <p className="text-sm text-zinc-400">Folder B — the Gachakingdoms identity. Read-only after Phase 1.</p>
      <Card>
        <CardHeader>
          <CardTitle>Files</CardTitle>
        </CardHeader>
        <CardBody className="space-y-2">
          {files.map((f) => (
            <div key={f.path} className="border border-brand-border rounded p-3 bg-black/20">
              <div className="flex items-center justify-between mb-2">
                <div className="font-mono text-xs text-zinc-200">{f.path}</div>
                <div className="text-[10px] text-zinc-500">{f.size} bytes</div>
              </div>
              {f.preview && (
                <pre className="text-[11px] text-zinc-400 whitespace-pre-wrap max-h-48 overflow-auto bg-black/40 p-2 rounded">
                  {f.preview}
                </pre>
              )}
            </div>
          ))}
        </CardBody>
      </Card>
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
