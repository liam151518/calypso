import { useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type Artifact = {
  treatment?: {
    audience?: string;
    tone?: string;
    format?: string;
    budget_usd?: number;
    promise?: string;
    cta?: string;
    risks?: string[];
  };
  scenes?: Array<{ index: number; slug: string; description: string; duration_s: number }>;
  shots?: Array<{
    id: string;
    scene_index: number;
    framing: string;
    lens: string;
    motion: string;
    duration_s: number;
    description: string;
  }>;
  pipeline?: { nodes: unknown[]; edges: unknown[] };
  selected_refs?: Array<{ id: string; tags: string[] }>;
  forged_refs?: Array<{ job_id: string; prompt: string }>;
};

type LogEntry = { agent: string; msg: string };

type StudioResponse = {
  ok: true;
  log: LogEntry[];
  artifacts: Artifact;
  spent_usd: number;
  pipeline_id: number | null;
};

const PRESETS: Array<{ name: string; brief: string }> = [
  {
    name: "Idea2Brand",
    brief:
      "Playful reel for ecommerce founders. cta: Start your free trial today.",
  },
  {
    name: "Brief2Ad",
    brief:
      "Cinematic 16:9 hero spot for SaaS teams. Show three friends using the app on a train. Promise: ship faster. Promise: less chaos.",
  },
  {
    name: "Script2Storyboard",
    brief:
      "Bold premium 9:16 for indie hackers.\n1. Hook: late night laptop glow (2s)\n2. Problem: endless tab chaos (3s)\n3. Promise: one calm view (3s)\n4. Proof: testimonial (3s)\n5. CTA: start free (2s)",
  },
];

export function StudioPage() {
  const [brief, setBrief] = useState<string>(PRESETS[0].brief);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<StudioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await fetch("/api/studio/run", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brief }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
      setResult(j);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Studio</h1>
        <p className="text-sm text-muted-foreground">
          Give it an idea. Get a campaign.
        </p>
        <details className="mt-2 text-xs text-muted-foreground">
          <summary className="cursor-pointer select-none">
            What happens when I click Run?
          </summary>
          <div className="mt-2 space-y-1">
            <p>
              A chain of agents reads your brief and builds out a complete campaign.
              Director sets the tone. Screenwriter drafts scenes. Storyboard picks the
              shots. Reference Selector finds matching assets. Asset Forge makes new
              ones if needed. Producer wires it into a runnable pipeline. QC gives it a
              once-over.
            </p>
            <p>
              You see the artifacts at every step and can jump into the pipeline builder
              to tweak them.
            </p>
          </div>
        </details>
      </div>

      <Card className="space-y-3 p-4">
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <Button
              key={p.name}
              variant="outline"
              size="sm"
              onClick={() => setBrief(p.brief)}
              data-testid={`preset-${p.name}`}
            >
              {p.name}
            </Button>
          ))}
        </div>
        <Textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          className="min-h-[120px]"
          placeholder="Describe the campaign idea…"
          data-testid="studio-brief"
        />
        <div className="flex items-center justify-between">
          <div className="text-xs text-muted-foreground">
            {brief.length} chars
          </div>
          <Button onClick={run} disabled={running || brief.trim().length < 5}>
            {running ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" />
            )}
            Run studio
          </Button>
        </div>
        {error ? (
          <div className="text-xs text-destructive" data-testid="studio-error">
            {error}
          </div>
        ) : null}
      </Card>

      {result ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2" data-testid="studio-output">
          <ArtifactCard title="Treatment">
            {result.artifacts.treatment && (
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <Kv k="audience" v={result.artifacts.treatment.audience} />
                <Kv k="tone" v={result.artifacts.treatment.tone} />
                <Kv k="format" v={result.artifacts.treatment.format} />
                <Kv k="budget_usd" v={`$${result.artifacts.treatment.budget_usd}`} />
                <Kv k="promise" v={result.artifacts.treatment.promise} wide />
                <Kv k="cta" v={result.artifacts.treatment.cta} wide />
              </dl>
            )}
          </ArtifactCard>

          <ArtifactCard title={`Scenes (${result.artifacts.scenes?.length ?? 0})`}>
            <ul className="space-y-1 text-sm">
              {result.artifacts.scenes?.map((s) => (
                <li key={s.index} className="rounded-md border border-border p-2">
                  <span className="font-mono text-xs text-muted-foreground">
                    {s.index}. {s.slug}
                  </span>
                  <span className="ml-2">{s.description}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {s.duration_s}s
                  </span>
                </li>
              ))}
            </ul>
          </ArtifactCard>

          <ArtifactCard title={`Shots (${result.artifacts.shots?.length ?? 0})`}>
            <ul className="space-y-1 text-xs">
              {result.artifacts.shots?.slice(0, 8).map((s) => (
                <li key={s.id} className="rounded-md border border-border p-2">
                  <span className="font-mono">{s.id}</span> ·{" "}
                  {s.framing}/{s.lens}/{s.motion} · {s.duration_s}s
                </li>
              ))}
            </ul>
          </ArtifactCard>

          <ArtifactCard
            title={`Pipeline${result.pipeline_id ? ` (#${result.pipeline_id})` : ""}`}
          >
            <div className="text-sm">
              {result.artifacts.pipeline
                ? `${result.artifacts.pipeline.nodes.length} nodes · ${result.artifacts.pipeline.edges.length} edges`
                : "no pipeline"}
            </div>
            {result.pipeline_id ? (
              <a
                href={`/pipelines/${result.pipeline_id}`}
                className="mt-2 inline-block text-xs text-signal underline"
              >
                open in pipeline builder →
              </a>
            ) : null}
          </ArtifactCard>

          <ArtifactCard title="Agent log" wide>
            <ul className="space-y-1 font-mono text-xs">
              {result.log.map((e, i) => (
                <li key={i}>
                  <span className="text-muted-foreground">[{e.agent}]</span>{" "}
                  {e.msg}
                </li>
              ))}
            </ul>
          </ArtifactCard>
        </div>
      ) : (
        <Input className="hidden" aria-hidden />
      )}
    </div>
  );
}

function ArtifactCard({
  title,
  children,
  wide,
}: {
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <Card className={`p-4 ${wide ? "lg:col-span-2" : ""}`}>
      <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      {children}
    </Card>
  );
}

function Kv({ k, v, wide }: { k: string; v?: string | number | null; wide?: boolean }) {
  if (v == null) return null;
  return (
    <div className={wide ? "col-span-2" : ""}>
      <dt className="text-xs text-muted-foreground">{k}</dt>
      <dd className="text-sm">{v}</dd>
    </div>
  );
}
