import { Cog } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { KeyRow } from "@/components/domain/KeyRow";
import { Card, CardContent } from "@/components/ui/card";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import { useKeys } from "@/lib/query";

export function SettingsPage() {
  const keys = useKeys();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        meta="Operator · Settings"
        title="API keys"
        description="Stored in your local .env file. Never uploaded anywhere."
      />
      {keys.isLoading ? (
        <LoadingSkeleton rows={3} />
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-3 p-4">
            {keys.data?.map((k) => (
              <KeyRow key={k.env_var} k={k} />
            ))}
            <div className="flex items-center gap-2 pt-1 text-[11px] text-muted-foreground">
              <Cog className="h-3 w-3" />
              Changes take effect on the next request — no restart required.
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
