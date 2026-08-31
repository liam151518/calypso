import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface TagPillProps {
  tag: string;
  active?: boolean;
  onClick?: () => void;
  onRemove?: () => void;
  className?: string;
}

export function TagPill({
  tag,
  active,
  onClick,
  onRemove,
  className,
}: TagPillProps) {
  const interactive = !!(onClick || onRemove);
  return (
    <span
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={interactive ? onClick : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick?.();
              }
              if (e.key === "Backspace" && onRemove) {
                e.preventDefault();
                onRemove();
              }
            }
          : undefined
      }
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide transition-colors",
        active && "border-primary/40 bg-primary/10 text-primary",
        interactive &&
          "cursor-pointer hover:bg-accent hover:text-accent-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      {tag}
      {onRemove ? (
        <button
          type="button"
          aria-label={`Remove ${tag}`}
          className="-mr-1 rounded-sm p-0.5 hover:bg-background/60"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        >
          <X className="h-3 w-3" />
        </button>
      ) : null}
    </span>
  );
}
