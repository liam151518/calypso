import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Cog,
  Library,
  Palette,
  Sparkles,
  Clapperboard,
} from "lucide-react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { useDrafts } from "@/lib/query";

const ROUTES = [
  { to: "/generate", label: "Generate", hint: "Compose and run jobs", icon: Sparkles },
  { to: "/outputs", label: "Outputs", hint: "Past renders and prompts", icon: Clapperboard },
  { to: "/references", label: "References", hint: "Library of input assets", icon: Library },
  { to: "/brand", label: "Brand", hint: "Voice, palette, style guide", icon: Palette },
  { to: "/settings", label: "Settings", hint: "API keys", icon: Cog },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const drafts = useDrafts();

  useEffect(() => {
    function onOpen() {
      setOpen(true);
    }
    window.addEventListener("calypso:open-command", onOpen);
    return () => window.removeEventListener("calypso:open-command", onOpen);
  }, []);

  function go(to: string) {
    setOpen(false);
    navigate(to);
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search routes, drafts, actions…" autoFocus />
      <CommandList>
        <CommandEmpty>No results.</CommandEmpty>
        <CommandGroup heading="Navigation">
          {ROUTES.map((r) => (
            <CommandItem
              key={r.to}
              value={`nav ${r.label}`}
              onSelect={() => go(r.to)}
            >
              <r.icon className="h-4 w-4" />
              <span>{r.label}</span>
              <span className="ml-2 text-xs text-muted-foreground">{r.hint}</span>
              <ArrowRight className="ml-auto h-3 w-3 opacity-50" />
            </CommandItem>
          ))}
        </CommandGroup>
        {drafts.data?.drafts.length ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Drafts">
              {drafts.data.drafts.slice(0, 8).map((d) => (
                <CommandItem
                  key={d.id}
                  value={`draft ${d.name} ${d.body}`}
                  onSelect={() => {
                    setOpen(false);
                    navigate("/generate");
                  }}
                >
                  <Sparkles className="h-4 w-4" />
                  <span className="truncate">{d.name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {d.category || "general"}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        ) : null}
      </CommandList>
    </CommandDialog>
  );
}
