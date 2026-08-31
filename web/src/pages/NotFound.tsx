import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export function NotFoundPage() {
  return (
    <Card className="mx-auto max-w-lg">
      <CardContent className="flex flex-col items-center gap-4 p-10 text-center">
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          404
        </span>
        <h1 className="text-xl font-semibold">Page not found</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          The route you tried doesn't exist on this Calypso deployment.
        </p>
        <Button asChild>
          <Link to="/generate">
            <ArrowLeft className="h-4 w-4" />
            Back to Generate
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
