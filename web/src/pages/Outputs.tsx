import { Clapperboard } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import { OutputCell } from "@/components/domain/OutputCell";
import { useOutputs } from "@/lib/query";

export function OutputsPage() {
  const outputs = useOutputs();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        meta="Operator · Outputs"
        title="Generated videos"
        description="Past runs with their effective prompts, brand context, and source references."
      />
      {outputs.isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <LoadingSkeleton key={i} rows={2} />
          ))}
        </div>
      ) : !outputs.data?.length ? (
        <EmptyState
          icon={Clapperboard}
          title="No outputs yet"
          description="Run a generation on the Generate page — outputs will appear here once they finish."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {outputs.data.map((o) => (
            <OutputCell key={o.id} output={o} />
          ))}
        </div>
      )}
    </div>
  );
}
