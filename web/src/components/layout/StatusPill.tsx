import { Badge } from "@/components/ui/badge";
import type { Job } from "@/lib/types";

export function StatusPill({
  status,
  className,
}: {
  status: Job["status"] | string;
  className?: string;
}) {
  const variant = pillVariant(status);
  const label = pillLabel(status);
  return (
    <Badge variant={variant} className={className}>
      <span
        className="h-1.5 w-1.5 rounded-full bg-current"
        aria-hidden="true"
      />
      {label}
    </Badge>
  );
}

function pillVariant(status: string) {
  switch (status) {
    case "succeeded":
    case "ok":
      return "ok" as const;
    case "failed":
    case "err":
    case "error":
      return "err" as const;
    case "running":
    case "pending":
      return "warn" as const;
    case "cancelled":
      return "muted" as const;
    default:
      return "outline" as const;
  }
}

function pillLabel(status: string) {
  if (!status) return "Unknown";
  return status[0].toUpperCase() + status.slice(1);
}
