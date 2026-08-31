import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { Card, CardHeader, CardTitle, CardBody } from "@/components/Card";
import { Pill } from "@/components/Pill";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const data = await api.overview();

  if (!data) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold glow">Overview</h1>
        <Card>
          <CardBody>
            <div className="text-zinc-300">
              <div className="text-brand font-semibold mb-2">Backend offline</div>
              <div className="text-sm text-zinc-400 mb-4">
                Start the FastAPI backend on port 8765 to see live data:
              </div>
              <pre className="bg-black/40 p-3 rounded text-xs">
                {`cd ui\nnpm run backend`}
              </pre>
              <div className="text-xs text-zinc-500 mt-3">
                Or run both UI + backend together: <code>npm run dev:all</code>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }

  const allTestsPassing = data.tests_total > 0 && data.tests_pass === data.tests_total;
  const verifyOk = data.verify_fail === 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold glow">Overview</h1>
        <div className="flex gap-2">
          {allTestsPassing && <Pill tone="ok">Tests green</Pill>}
          {verifyOk && <Pill tone="ok">Verify green</Pill>}
          {data.adam_installed ? <Pill tone="ok">Adam ready</Pill> : <Pill tone="warn">Adam not installed</Pill>}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Tests passing" value={`${data.tests_pass}/${data.tests_total}`} tone={allTestsPassing ? "ok" : "warn"} />
        <StatCard label="Verify gate" value={`${data.verify_pass} pass / ${data.verify_fail} fail`} tone={verifyOk ? "ok" : "error"} />
        <StatCard label="Scripts" value={data.scripts} />
        <StatCard label="Workflows" value={data.workflows} />
        <StatCard label="Brand files" value={data.brand_files} />
        <StatCard label="References" value={data.references} />
        <StatCard label="Adam skills" value={data.adam_installed ? "installed" : "missing"} tone={data.adam_installed ? "ok" : "warn"} />
        <StatCard label="Backend" value="online" tone="ok" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>What's here</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-sm text-zinc-300">
            This is the local dashboard for the Gachakingdoms Reference-Driven Ad Pipeline.
            All five phases are scaffolded. Use the sidebar to inspect scripts, brand pack,
            workflows, tests, and accounts. Run anything via the Scripts and Tests pages.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
