import { useMemo, useState } from "react";
import { Sparkles, Trash2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  useSkills,
  useToggleSkill,
  useUpdateSkill,
  useDeleteSkill,
  useCreateSkill,
  useTestSkill,
  useLLMProviders,
} from "@/lib/query";

export function SkillsPage() {
  const skillsQuery = useSkills();
  const providersQuery = useLLMProviders();

  const skills = skillsQuery.data?.skills ?? [];
  const providers = providersQuery.data?.providers ?? [];
  const activeProvider = providersQuery.data?.active ?? "";

  const enabledCount = useMemo(
    () => skills.filter((s) => s.enabled).length,
    [skills],
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        meta="Skills"
        title="Prompt enhancement skills"
        description={`${enabledCount} of ${skills.length} skills enabled. Skills inject markdown into every LLM call (pre) and apply post-process transforms to the response.`}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">LLM backend</CardTitle>
        </CardHeader>
        <CardContent>
          {providersQuery.isLoading ? (
            <LoadingSkeleton rows={2} />
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {providers.map((p) => {
                const isActive = p.name.toLowerCase() === activeProvider;
                return (
                  <div
                    key={p.env_var}
                    className={cn(
                      "flex flex-col gap-1 rounded-md border p-3 text-xs",
                      isActive ? "border-primary bg-primary/5" : "border-border",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{p.name}</span>
                      {isActive && <Badge variant="ok">active</Badge>}
                    </div>
                    <span className="text-[11px] text-muted-foreground">
                      Model: <code>{p.default_model}</code>
                    </span>
                    <span className="text-[11px]">
                      {p.is_set ? (
                        <Badge variant="ok" className="mt-1">key set</Badge>
                      ) : (
                        <Badge variant="warn" className="mt-1">key missing</Badge>
                      )}
                    </span>
                    <a
                      href={p.docs_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-primary underline-offset-2 hover:underline"
                    >
                      Get a key →
                    </a>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <NewSkillCard />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {skillsQuery.isLoading && <LoadingSkeleton rows={4} />}
        {skills.map((skill) => (
          <SkillCard key={skill.slug} skill={skill} />
        ))}
      </div>
    </div>
  );
}

function NewSkillCard() {
  const create = useCreateSkill();
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [content, setContent] = useState("");

  function submit() {
    if (!slug.trim()) {
      toast.error("Slug is required");
      return;
    }
    if (!content.trim()) {
      toast.error("Body is required");
      return;
    }
    create.mutate(
      { slug: slug.trim(), name: name.trim() || undefined, content_md: content },
      {
        onSuccess: () => {
          toast.success(`Skill ${slug} created`);
          setSlug("");
          setName("");
          setContent("");
        },
        onError: (err) => toast.error(err.message),
      },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Add a custom skill</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ns-slug" className="text-xs">Slug</Label>
            <Input
              id="ns-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="my_brand_voice"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ns-name" className="text-xs">Display name</Label>
            <Input
              id="ns-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Brand Voice"
            />
          </div>
        </div>
        <div className="mt-3 flex flex-col gap-1.5">
          <Label htmlFor="ns-body" className="text-xs">Body (markdown)</Label>
          <Textarea
            id="ns-body"
            rows={4}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Skill instructions injected as a <skill> block in every LLM prompt."
          />
        </div>
        <div className="mt-3 flex justify-end">
          <Button onClick={submit} disabled={create.isPending}>
            <Sparkles className="mr-1 h-3.5 w-3.5" />
            Create skill
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function SkillCard({ skill }: { skill: import("@/lib/types").Skill }) {
  const toggle = useToggleSkill();
  const update = useUpdateSkill();
  const del = useDeleteSkill();
  const test = useTestSkill();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(skill.name);
  const [content, setContent] = useState(skill.content_md);
  const [postRe, setPostRe] = useState(skill.post_process_re ?? "");
  const [sample, setSample] = useState("");

  const testResult = test.data;

  function save() {
    update.mutate(
      {
        slug: skill.slug,
        body: {
          name: name.trim() || skill.slug,
          content_md: content,
          post_process_re: postRe.trim() || null,
        },
      },
      {
        onSuccess: () => {
          toast.success("Saved");
          setEditing(false);
        },
        onError: (err) => toast.error(err.message),
      },
    );
  }

  function runTest() {
    if (!sample.trim()) {
      toast.error("Sample prompt required");
      return;
    }
    test.mutate(
      { slug: skill.slug, sample },
      {
        onError: (err) => toast.error(err.message),
      },
    );
  }

  return (
    <Card className={cn(skill.enabled ? "border-primary/40" : "border-border")}>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            {skill.name}
            {skill.builtin && <Badge variant="muted">built-in</Badge>}
            {!skill.builtin && <Badge variant="ok">custom</Badge>}
          </CardTitle>
          <Switch
            checked={skill.enabled}
            onCheckedChange={(v) =>
              toggle.mutate({ slug: skill.slug, enabled: v })
            }
            aria-label={`Toggle ${skill.name}`}
          />
        </div>
        {skill.description && (
          <p className="text-xs text-muted-foreground">{skill.description}</p>
        )}
        {skill.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {skill.tags.map((t) => (
              <Badge key={t} variant="muted" className="text-[10px]">
                {t}
              </Badge>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {editing ? (
          <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px]">Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px]">Body</Label>
              <Textarea
                rows={5}
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-[11px]">Post-process regex (optional)</Label>
              <Input
                value={postRe}
                onChange={(e) => setPostRe(e.target.value)}
                placeholder="(?i)\b(just|very)\b"
                className="font-mono"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={save} disabled={update.isPending}>
                Save
              </Button>
            </div>
          </div>
        ) : (
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-[11px] leading-relaxed text-foreground">
            {skill.content_md || <em className="text-muted-foreground">empty body</em>}
          </pre>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
          {!editing && (
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              Edit
            </Button>
          )}
          <Input
            value={sample}
            onChange={(e) => setSample(e.target.value)}
            placeholder="Sample prompt to test…"
            className="h-8 flex-1 min-w-[10rem] text-xs"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={runTest}
            disabled={test.isPending}
          >
            {test.isPending ? (
              <RefreshCw className="mr-1 h-3 w-3 animate-spin" />
            ) : (
              <Sparkles className="mr-1 h-3 w-3" />
            )}
            Test
          </Button>
          {!skill.builtin && (
            <Button
              size="sm"
              variant="ghost"
              className="text-err hover:text-err"
              onClick={() => {
                if (confirm(`Delete ${skill.slug}?`)) {
                  del.mutate(skill.slug, {
                    onSuccess: () => toast.success("Deleted"),
                    onError: (err) => toast.error(err.message),
                  });
                }
              }}
            >
              <Trash2 className="mr-1 h-3 w-3" />
              Delete
            </Button>
          )}
        </div>

        {testResult && (
          <div className="mt-3 grid grid-cols-1 gap-2 border-t pt-3 text-[11px]">
            <div className="flex flex-col gap-1">
              <span className="font-medium uppercase tracking-wide text-muted-foreground">
                Injected system
              </span>
              <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-md bg-muted/30 p-2">
                {testResult.injected_system}
              </pre>
            </div>
            {skill.post_process_re && (
              <div className="flex flex-col gap-1">
                <span className="font-medium uppercase tracking-wide text-muted-foreground">
                  Post-processed
                </span>
                <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-md bg-muted/30 p-2">
                  {testResult.post_processed}
                </pre>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
