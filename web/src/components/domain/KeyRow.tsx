import { useState } from "react";
import { Save, Trash2, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useDeleteKey, useSetKey } from "@/lib/query";
import type { KeyStatus } from "@/lib/types";

export function KeyRow({ k }: { k: KeyStatus }) {
  const [value, setValue] = useState("");
  const [show, setShow] = useState(false);
  const set = useSetKey();
  const del = useDeleteKey();

  return (
    <div
      data-testid={`key-row-${k.env_var}`}
      className="grid grid-cols-1 gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-[1fr_2fr_auto] md:items-end"
    >
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <Label htmlFor={`input-${k.env_var}`}>{k.env_var}</Label>
          {k.is_set ? (
            <Badge variant="ok">set</Badge>
          ) : (
            <Badge variant="muted">not set</Badge>
          )}
        </div>
        <span className="text-xs text-muted-foreground">{k.service}</span>
        {k.is_set && !show ? (
          <code className="font-mono text-[11px] text-foreground/80">
            {k.masked}
          </code>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        <div className="relative w-full">
          <Input
            id={`input-${k.env_var}`}
            type={show ? "text" : "password"}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={k.placeholder}
            autoComplete="off"
            className="pr-9 font-mono"
          />
          <button
            type="button"
            aria-label={show ? "Hide value" : "Show value"}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            onClick={() => setShow((v) => !v)}
          >
            {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          onClick={() =>
            set.mutate(
              { env_var: k.env_var, value },
              {
                onSuccess: () => {
                  toast.success(`Saved ${k.env_var}`);
                  setValue("");
                },
                onError: (err) =>
                  toast.error(
                    err instanceof Error ? err.message : "Save failed",
                  ),
              },
            )
          }
          disabled={!value || set.isPending}
        >
          <Save className="h-4 w-4" />
          Save
        </Button>
        {k.is_set ? (
          <Dialog>
            <DialogTrigger asChild>
              <Button size="sm" variant="ghost" className="text-muted-foreground hover:text-err">
                <Trash2 className="h-4 w-4" />
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete {k.env_var}?</DialogTitle>
                <DialogDescription>
                  Removes this key from your local <code>.env</code>. You can
                  re-add it later.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="destructive"
                  onClick={() =>
                    del.mutate(k.env_var, {
                      onSuccess: () => toast.success(`Deleted ${k.env_var}`),
                    })
                  }
                  disabled={del.isPending}
                >
                  Delete
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        ) : null}
      </div>
    </div>
  );
}
