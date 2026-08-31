import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { JobCard } from "./JobCard";
import type { Job } from "@/lib/types";

interface BatchBlockProps {
  batchId: string;
  jobs: Job[];
}

export function BatchBlock({ batchId, jobs }: BatchBlockProps) {
  const total = jobs.length;
  const succeeded = jobs.filter((j) => j.status === "succeeded").length;
  const failed = jobs.filter((j) => j.status === "failed").length;
  const running = jobs.filter(
    (j) => j.status === "running" || j.status === "pending",
  ).length;

  return (
    <Card data-testid={`batch-${batchId}`}>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge variant="muted" className="font-mono">
            Batch
          </Badge>
          <span className="font-mono text-xs text-muted-foreground">
            {batchId}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant={failed > 0 ? "err" : "muted"}>
            {failed} failed
          </Badge>
          <Badge variant="muted">{running} running</Badge>
          <Badge variant={succeeded === total ? "ok" : "muted"}>
            {succeeded}/{total} succeeded
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {jobs.map((j) => (
          <JobCard key={j.id} job={j} />
        ))}
      </CardContent>
    </Card>
  );
}
