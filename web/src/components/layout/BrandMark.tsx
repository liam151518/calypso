import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-primary",
        className,
      )}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="square"
        strokeLinejoin="miter"
        className="h-4 w-4"
      >
        <rect x="3" y="3" width="18" height="18" rx="1" />
        <line x1="3" y1="21" x2="21" y2="3" strokeWidth={2} />
      </svg>
    </div>
  );
}
