import { useState } from "react";
import {
  ExternalLink,
  Eye,
  EyeOff,
  Save,
  ShieldAlert,
  Trash2,
  Zap,
} from "lucide-react";
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

interface KeyRowProps {
  k: KeyStatus;
  onTest?: () => void;
  testing?: boolean;
}

export function KeyRow({ k, onTest, testing }: KeyRowProps) {
  const [value, setValue] = useState("");
  const [show, setShow] = useState(false);
  const set = useSetKey();
  const del = useDeleteKey();

  const save = () =>
    set.mutate(
      { env_var: k.env_var, value },
      {
        onSuccess: () => {
          toast.success(`Saved ${k.env_var}`);
          setValue("");
        },
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Save failed"),
      },
    );

  const remove = () =>
    del.mutate(k.env_var, {
      onSuccess: () => toast.success(`Deleted ${k.env_var}`),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Delete failed"),
    });

  return (
    <div
      data-testid={`key-row-${k.env_var}`}
      className="grid grid-cols-1 gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-[1.4fr_2fr_auto] md:items-end"
    >
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <Label htmlFor={`input-${k.env_var}`} className="font-mono">
            {k.env_var}
          </Label>
          {k.required ? (
            <Badge variant="warn" className="gap-1">
              <ShieldAlert className="h-3 w-3" /> required
            </Badge>
          ) : (
            <Badge variant="muted">optional</Badge>
          )}
          {k.is_set ? (
            <Badge variant="ok">set</Badge>
          ) : (
            <Badge variant="muted">not set</Badge>
          )}
        </div>
        <span className="text-xs text-muted-foreground">{k.service}</span>
        {k.description ? (
          <span className="text-xs text-muted-foreground">
            {k.description}
          </span>
        ) : null}
        {k.docs_url ? (
          <a
            href={k.docs_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex w-fit items-center gap-1 text-[11px] text-primary hover:underline"
          >
            Get this key <ExternalLink className="h-3 w-3" />
          </a>
        ) : null}
        {k.is_set && !show && k.masked ? (
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
            placeholder={k.placeholder || "paste the secret here"}
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
          onClick={save}
          disabled={!value || set.isPending}
        >
          <Save className="h-4 w-4" />
          Save
        </Button>
        {onTest ? (
          <Button
            size="sm"
            variant="outline"
            onClick={onTest}
            disabled={!k.is_set || testing}
            title={k.is_set ? "Run a sanity check" : "Set the key first"}
          >
            <Zap className="h-4 w-4" />
            {testing ? "Testing…" : "Test"}
          </Button>
        ) : null}
        {k.is_set ? (
          <Dialog>
            <DialogTrigger asChild>
              <Button
                size="sm"
                variant="ghost"
                className="text-muted-foreground hover:text-err"
                aria-label={`Delete ${k.env_var}`}
              >
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
                  onClick={remove}
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
