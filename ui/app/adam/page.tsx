import { api } from "@/lib/api";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/Card";
import { Pill } from "@/components/Pill";

export const dynamic = "force-dynamic";

export default async function AdamPage() {
  const status = await api.adamStatus();
  if (!status) return <Offline />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold glow">Adam</h1>
        <div className="flex gap-2">
          <Pill tone={status.installed_at_project_level ? "ok" : "warn"}>
            {status.installed_at_project_level ? "Project install" : "Project: missing"}
          </Pill>
          <Pill tone={status.installed_at_user_level ? "ok" : "neutral"}>
            {status.installed_at_user_level ? "User install" : "User: missing"}
          </Pill>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Context files</CardTitle>
        </CardHeader>
        <CardBody>
          {status.context_files.length === 0 ? (
            <div className="text-sm text-zinc-400">No <code>adam/context/</code> files yet — run <code>calibrate</code>.</div>
          ) : (
            <ul className="space-y-1">
              {status.context_files.map((f) => (
                <li key={f} className="font-mono text-xs text-zinc-300">{f}</li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Project skills (.cursor/skills)</CardTitle>
        </CardHeader>
        <CardBody>
          {status.project_skills.length === 0 ? (
            <div className="text-sm text-zinc-400">No project-level skills installed. Run <code>setup-adam</code> to install.</div>
          ) : (
            <div className="flex flex-wrap gap-1">
              {status.project_skills.map((s) => (
                <Pill key={s} tone="info">{s}</Pill>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>User-level skills (~/.cursor/skills)</CardTitle>
        </CardHeader>
        <CardBody>
          {status.user_skills.length === 0 ? (
            <div className="text-sm text-zinc-400">No user-level skills installed.</div>
          ) : (
            <div className="flex flex-wrap gap-1">
              {status.user_skills.map((s) => (
                <Pill key={s} tone="neutral">{s}</Pill>
              ))}
            </div>
          )}
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
