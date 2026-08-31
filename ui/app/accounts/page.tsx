import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/Card";
import { Pill } from "@/components/Pill";

export const dynamic = "force-dynamic";

export default async function AccountsPage() {
  const accounts = await api.accounts();
  if (!accounts) return <Offline />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold glow">Accounts</h1>
      <p className="text-sm text-zinc-400">Third-party accounts and API credentials. See <code>docs/accounts.md</code> for the full checklist.</p>
      <Card>
        <CardHeader>
          <CardTitle>Required services</CardTitle>
        </CardHeader>
        <CardBody className="space-y-2">
          {accounts.map((a) => (
            <div key={a.name} className="border border-brand-border rounded p-3 bg-black/20 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <div className="font-semibold text-sm">{a.name}</div>
                  {a.required ? <Pill tone="warn">required</Pill> : <Pill tone="neutral">optional</Pill>}
                  {a.env_present ? <Pill tone="ok">env set</Pill> : <Pill tone="error">missing</Pill>}
                </div>
                <div className="text-xs text-zinc-400 mb-1">{a.purpose}</div>
                <a href={a.url} target="_blank" className="text-[10px] text-brand-accent font-mono break-all">{a.url}</a>
                <div className="text-[10px] text-zinc-500 font-mono mt-1">env: {a.env_key}</div>
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
