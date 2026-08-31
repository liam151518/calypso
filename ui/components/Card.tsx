import { cn } from "@/lib/cn";

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("card", className)}>{children}</div>;
}

export function CardHeader({ children }: { children: React.ReactNode }) {
  return <div className="px-5 pt-4 pb-2 border-b border-brand-border">{children}</div>;
}

export function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h3 className={cn("text-sm font-semibold text-zinc-100", className)}>{children}</h3>;
}

export function CardBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("p-5", className)}>{children}</div>;
}
