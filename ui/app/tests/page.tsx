import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/Card";
import { Pill } from "@/components/Pill";
import { TestRunner } from "@/components/TestRunner";

export const dynamic = "force-dynamic";

export default async function TestsPage() {
  const tests = await api.tests();
  if (!tests) return <Offline />;

  const allPass = tests.failed === 0 && tests.passed > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold glow">Tests</h1>
        <div className="flex gap-2">
          <Pill tone={allPass ? "ok" : "error"}>
            {tests.passed}/{tests.total} passing
          </Pill>
        </div>
      </div>
      <TestRunner />
      <Card>
        <CardHeader>
          <CardTitle>By file</CardTitle>
        </CardHeader>
        <CardBody className="space-y-2">
          {tests.files.map((f) => (
            <div key={f.file} className="flex items-center justify-between border border-brand-border rounded px-3 py-2 bg-black/20">
              <div className="font-mono text-xs text-zinc-200">{f.file}</div>
              <div className="flex items-center gap-2 text-xs">
                <Pill tone={f.failed === 0 ? "ok" : "error"}>
                  {f.passed} pass
                </Pill>
                {f.failed > 0 && <Pill tone="error">{f.failed} fail</Pill>}
              </div>
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
