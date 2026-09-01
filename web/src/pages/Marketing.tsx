import { useState } from "react";
import {
  Calendar,
  Globe,
  Mail,
  Megaphone,
  PieChart,
  Plus,
  Send,
  Trash2,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type Tab = "contacts" | "campaigns" | "pages" | "social" | "analytics" | "scheduler";

type Contact = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  tags: string[];
  consent_marketing: boolean;
  unsubscribed_at: number | null;
};

type Campaign = {
  id: number;
  name: string;
  subject: string;
  channel: string;
  status: string;
  send_at: number | null;
  body_html: string;
};

type LandingPage = {
  id: number;
  slug: string;
  title: string;
  published: boolean;
  consent_text: string;
};

type SocialPost = {
  id: number;
  platform: string;
  body: string;
  status: string;
  scheduled_at: number | null;
  char_limit: number;
  over_limit: boolean;
};

const TABS: Array<{ id: Tab; label: string; icon: typeof Users }> = [
  { id: "contacts", label: "Contacts", icon: Users },
  { id: "campaigns", label: "Campaigns", icon: Mail },
  { id: "pages", label: "Pages", icon: Globe },
  { id: "social", label: "Social", icon: Megaphone },
  { id: "scheduler", label: "Scheduler", icon: Calendar },
  { id: "analytics", label: "Analytics", icon: PieChart },
];

export function MarketingPage() {
  const [tab, setTab] = useState<Tab>("contacts");
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Marketing</h1>
        <p className="text-sm text-muted-foreground">
          Contacts, campaigns, pages, social, scheduler, analytics. One control room
          for getting the word out.
        </p>
        <details className="mt-2 text-xs text-muted-foreground">
          <summary className="cursor-pointer select-none">
            Where do I start?
          </summary>
          <div className="mt-2 space-y-1">
            <p>
              Start with Contacts. Add a few people and tag them. Then build a
              Campaign that sends them an email, or post to Social, or both.
            </p>
            <p>
              The Scheduler lets you set things to fire later. Analytics tracks opens,
              clicks, and unsubscribes so you know what works.
            </p>
          </div>
        </details>
      </div>

      <div className="flex flex-wrap gap-2" data-testid="marketing-tabs">
        {TABS.map((t) => (
          <Button
            key={t.id}
            size="sm"
            variant={tab === t.id ? "default" : "outline"}
            onClick={() => setTab(t.id)}
            data-testid={`tab-${t.id}`}
          >
            <t.icon className="mr-1 h-4 w-4" /> {t.label}
          </Button>
        ))}
      </div>

      {tab === "contacts" ? <ContactsTab /> : null}
      {tab === "campaigns" ? <CampaignsTab /> : null}
      {tab === "pages" ? <PagesTab /> : null}
      {tab === "social" ? <SocialTab /> : null}
      {tab === "scheduler" ? <SchedulerTab /> : null}
      {tab === "analytics" ? <AnalyticsTab /> : null}
    </div>
  );
}

function ContactsTab() {
  const [items, setItems] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [consent, setConsent] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const r = await fetch("/api/contacts");
      const j = await r.json();
      setItems(j.contacts ?? []);
    } finally {
      setLoading(false);
    }
  }

  async function add() {
    if (!email.includes("@")) return;
    await fetch("/api/contacts", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        first_name: firstName,
        consent_marketing: consent,
      }),
    });
    setEmail("");
    setFirstName("");
    refresh();
  }

  async function remove(id: number) {
    await fetch(`/api/contacts/${id}`, { method: "DELETE" });
    refresh();
  }

  // First render
  if (loading && items.length === 0) {
    refresh();
    return <div className="text-sm text-muted-foreground">Loading…</div>;
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-2 p-4">
        <h3 className="text-sm font-medium">Add a contact</h3>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <Input
            placeholder="first name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
          />
          <Input
            placeholder="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            data-testid="contact-email"
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            consent
          </label>
          <Button onClick={add} disabled={!email.includes("@")}>
            <Plus className="mr-1 h-4 w-4" /> Add
          </Button>
        </div>
      </Card>
      <Card className="p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
              <th className="p-3">email</th>
              <th className="p-3">name</th>
              <th className="p-3">tags</th>
              <th className="p-3">status</th>
              <th className="p-3" />
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} className="border-b border-border/50">
                <td className="p-3">{c.email}</td>
                <td className="p-3">
                  {c.first_name} {c.last_name}
                </td>
                <td className="p-3 text-xs">
                  {c.tags.map((t) => (
                    <span
                      key={t}
                      className="mr-1 rounded bg-card/60 px-2 py-0.5"
                    >
                      {t}
                    </span>
                  ))}
                </td>
                <td className="p-3 text-xs">
                  {c.unsubscribed_at ? (
                    <span className="text-destructive">unsubscribed</span>
                  ) : c.consent_marketing ? (
                    <span className="text-green-500">opted-in</span>
                  ) : (
                    <span className="text-muted-foreground">no consent</span>
                  )}
                </td>
                <td className="p-3">
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => remove(c.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </td>
              </tr>
            ))}
            {items.length === 0 ? (
              <tr>
                <td className="p-3 text-muted-foreground" colSpan={5}>
                  No contacts yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function CampaignsTab() {
  const [items, setItems] = useState<Campaign[]>([]);
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");

  async function refresh() {
    const r = await fetch("/api/campaigns");
    const j = await r.json();
    setItems(j.campaigns ?? []);
  }

  async function create() {
    if (!name) return;
    await fetch("/api/campaigns", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, subject, body_html: body }),
    });
    setName("");
    setSubject("");
    setBody("");
    refresh();
  }

  async function send(id: number) {
    await fetch(`/api/campaigns/${id}/send`, {
      method: "POST",
      credentials: "same-origin",
    });
    refresh();
  }

  if (items.length === 0) refresh();

  return (
    <div className="space-y-4">
      <Card className="space-y-2 p-4">
        <h3 className="text-sm font-medium">New campaign</h3>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <Input
            placeholder="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            placeholder="subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          />
        </div>
        <Textarea
          placeholder="body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          className="min-h-[80px]"
        />
        <div className="flex justify-end">
          <Button onClick={create} disabled={!name}>
            <Plus className="mr-1 h-4 w-4" /> Save draft
          </Button>
        </div>
      </Card>
      <div className="space-y-2">
        {items.map((c) => (
          <Card key={c.id} className="flex items-center justify-between p-3">
            <div>
              <div className="font-medium">{c.name}</div>
              <div className="text-xs text-muted-foreground">
                {c.channel} · {c.status} · {c.subject || "(no subject)"}
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => send(c.id)}
              disabled={c.status === "sent"}
            >
              <Send className="mr-1 h-3 w-3" /> Send
            </Button>
          </Card>
        ))}
        {items.length === 0 ? (
          <div className="text-sm text-muted-foreground">No campaigns.</div>
        ) : null}
      </div>
    </div>
  );
}

function PagesTab() {
  const [items, setItems] = useState<LandingPage[]>([]);
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [consent, setConsent] = useState("");

  async function refresh() {
    const r = await fetch("/api/pages");
    const j = await r.json();
    setItems(j.pages ?? []);
  }
  async function create() {
    if (!title) return;
    await fetch("/api/pages", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug: slug || title, title, consent_text: consent }),
    });
    setSlug("");
    setTitle("");
    setConsent("");
    refresh();
  }
  if (items.length === 0) refresh();

  return (
    <div className="space-y-4">
      <Card className="space-y-2 p-4">
        <h3 className="text-sm font-medium">New landing page</h3>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <Input
            placeholder="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <Input
            placeholder="slug (optional)"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
          />
          <Input
            placeholder="consent text"
            value={consent}
            onChange={(e) => setConsent(e.target.value)}
          />
        </div>
        <div className="flex justify-end">
          <Button onClick={create} disabled={!title}>
            <Plus className="mr-1 h-4 w-4" /> Create
          </Button>
        </div>
      </Card>
      <div className="space-y-2">
        {items.map((p) => (
          <Card key={p.id} className="flex items-center justify-between p-3">
            <div>
              <div className="font-medium">{p.title}</div>
              <div className="text-xs text-muted-foreground">
                /{p.slug} · {p.published ? "published" : "draft"}
              </div>
            </div>
          </Card>
        ))}
        {items.length === 0 ? (
          <div className="text-sm text-muted-foreground">No pages.</div>
        ) : null}
      </div>
    </div>
  );
}

function SocialTab() {
  const [items, setItems] = useState<SocialPost[]>([]);
  const [platform, setPlatform] = useState("x");
  const [body, setBody] = useState("");

  async function refresh() {
    const r = await fetch("/api/social");
    const j = await r.json();
    setItems(j.posts ?? []);
  }
  async function create() {
    if (!body) return;
    await fetch("/api/social", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform, body }),
    });
    setBody("");
    refresh();
  }
  if (items.length === 0) refresh();

  return (
    <div className="space-y-4">
      <Card className="space-y-2 p-4">
        <h3 className="text-sm font-medium">New post</h3>
        <div className="flex gap-2">
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="rounded-md border border-border bg-card px-2 text-sm"
            data-testid="social-platform"
          >
            <option value="x">X</option>
            <option value="linkedin">LinkedIn</option>
            <option value="instagram">Instagram</option>
            <option value="tiktok">TikTok</option>
            <option value="facebook">Facebook</option>
          </select>
          <Input
            placeholder="body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            data-testid="social-body"
            className="flex-1"
          />
          <Button onClick={create} disabled={!body}>
            <Plus className="mr-1 h-4 w-4" /> Save
          </Button>
        </div>
      </Card>
      <div className="space-y-2">
        {items.map((p) => (
          <Card key={p.id} className="p-3">
            <div className="text-xs text-muted-foreground">
              {p.platform} · {p.status} · {p.body.length}/{p.char_limit}
              {p.over_limit ? (
                <span className="ml-2 text-destructive">over limit</span>
              ) : null}
            </div>
            <div className="mt-1 text-sm">{p.body}</div>
          </Card>
        ))}
        {items.length === 0 ? (
          <div className="text-sm text-muted-foreground">No posts.</div>
        ) : null}
      </div>
    </div>
  );
}

function SchedulerTab() {
  const [items, setItems] = useState<Array<{ id: number; name: string; kind: string; status: string; run_at: number }>>([]);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("send_campaign");

  async function refresh() {
    const r = await fetch("/api/scheduler/jobs");
    const j = await r.json();
    setItems(j.jobs ?? []);
  }
  async function create() {
    if (!name) return;
    await fetch("/api/scheduler/jobs", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        kind,
        run_at: Math.floor(Date.now() / 1000) + 5,
      }),
    });
    setName("");
    refresh();
  }
  if (items.length === 0) refresh();

  return (
    <div className="space-y-4">
      <Card className="space-y-2 p-4">
        <h3 className="text-sm font-medium">Schedule a job (5s from now)</h3>
        <div className="flex gap-2">
          <Input
            placeholder="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            className="rounded-md border border-border bg-card px-2 text-sm"
          >
            <option value="send_campaign">send_campaign</option>
            <option value="publish_social">publish_social</option>
            <option value="run_pipeline">run_pipeline</option>
          </select>
          <Button onClick={create} disabled={!name}>
            <Plus className="mr-1 h-4 w-4" /> Schedule
          </Button>
        </div>
      </Card>
      <Card className="p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
              <th className="p-3">id</th>
              <th className="p-3">name</th>
              <th className="p-3">kind</th>
              <th className="p-3">status</th>
              <th className="p-3">run_at</th>
            </tr>
          </thead>
          <tbody>
            {items.map((j) => (
              <tr key={j.id} className="border-b border-border/50">
                <td className="p-3">{j.id}</td>
                <td className="p-3">{j.name}</td>
                <td className="p-3">{j.kind}</td>
                <td className="p-3">{j.status}</td>
                <td className="p-3 text-xs">
                  {new Date(j.run_at * 1000).toLocaleString()}
                </td>
              </tr>
            ))}
            {items.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-3 text-muted-foreground">
                  No jobs queued.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function AnalyticsTab() {
  const [data, setData] = useState<Record<string, { count: number; sum: number }>>({});
  const [days, setDays] = useState(7);

  async function refresh() {
    const r = await fetch(`/api/analytics/aggregate?days=${days}`);
    const j = await r.json();
    setData(j.aggregate ?? {});
  }
  if (Object.keys(data).length === 0) refresh();

  const entries = Object.entries(data).filter(([, v]) => v.count > 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <label className="text-sm">window:</label>
        <Input
          type="number"
          min={1}
          max={365}
          value={days}
          onChange={(e) => {
            setDays(parseInt(e.target.value || "7", 10));
            refresh();
          }}
          className="w-24"
        />
        <span className="text-xs text-muted-foreground">days</span>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {entries.length === 0 ? (
          <Card className="col-span-full p-4 text-sm text-muted-foreground">
            No events yet. Send a campaign or schedule a post to start tracking.
          </Card>
        ) : null}
        {entries.map(([k, v]) => (
          <Card key={k} className="p-4">
            <div className="text-xs uppercase text-muted-foreground">{k}</div>
            <div className="mt-1 text-2xl">{v.count}</div>
            {v.sum ? (
              <div className="text-xs text-muted-foreground">
                sum: ${v.sum.toFixed(2)}
              </div>
            ) : null}
          </Card>
        ))}
      </div>
    </div>
  );
}
