"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import {
  LayoutDashboard,
  ListChecks,
  Code2,
  Palette,
  GitBranch,
  FlaskConical,
  KeyRound,
  Brain,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/phases", label: "Phases", icon: ListChecks },
  { href: "/scripts", label: "Scripts", icon: Code2 },
  { href: "/brand", label: "Brand Pack", icon: Palette },
  { href: "/workflows", label: "Workflows", icon: GitBranch },
  { href: "/tests", label: "Tests", icon: FlaskConical },
  { href: "/accounts", label: "Accounts", icon: KeyRound },
  { href: "/adam", label: "Adam", icon: Brain },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-60 shrink-0 border-r border-brand-border bg-brand-ink p-4 flex flex-col gap-1">
      <div className="px-2 py-4">
        <div className="text-[11px] uppercase tracking-widest text-brand-muted">Gachakingdoms</div>
        <div className="text-lg font-bold glow">Pipeline UI</div>
      </div>
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = path === href || (href !== "/" && path.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              active
                ? "bg-brand/15 text-brand border border-brand/30"
                : "text-zinc-300 hover:bg-white/5 border border-transparent",
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        );
      })}
      <div className="mt-auto text-[10px] text-zinc-500 px-2 py-3">
        v0.1 · local dev
      </div>
    </aside>
  );
}
