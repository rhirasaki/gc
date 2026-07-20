import { useEffect, useState } from "react";
import { Button, Card, Eyebrow } from "../ui";

type RouteRow = { provider: string; model: string; default_provider: string; default_model: string };
type SettingsT = {
  ai_routes: Record<string, RouteRow>;
  providers: string[];
  budget_alert_usd: number;
  chunk_threshold_mb: number;
  data_root: string;
};

const TASK_HELP: Record<string, string> = {
  classification: "Vision tagging per photo — cheap and batchable; cached forever per image.",
  narrative: "Chapter prose. This is the product — the strongest model belongs here.",
  research: "Grounded historical and cultural context, with sources.",
  chat: "Command parsing for the chat panel — fast and cheap, runs on every message.",
  grounding: "The adversarial fact-check pass over generated narrative.",
  synopsis: "Short project summaries for dashboard cards.",
  layout: "Hero-image tie-breaking only; layout itself is deterministic.",
  ingestion: "Note segmentation and extraction.",
};

export default function Settings() {
  const [s, setS] = useState<SettingsT | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/api/settings").then((r) => r.json()).then(setS).catch(() => {});
  }, []);
  if (!s) return <div className="text-ink-2 text-sm">Loading…</div>;

  const set = (task: string, field: "provider" | "model", value: string) =>
    setS({ ...s, ai_routes: { ...s.ai_routes, [task]: { ...s.ai_routes[task], [field]: value } } });

  async function save() {
    const body = Object.fromEntries(
      Object.entries(s!.ai_routes).map(([k, v]) => [k, { provider: v.provider, model: v.model }]),
    );
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ai_routes: body }),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <div className="max-w-3xl">
      <Eyebrow>Configuration</Eyebrow>
      <h1 className="display text-4xl mb-2">Settings</h1>
      <p className="text-sm text-ink-2 mb-8">
        Which model does which job. Projects can override any of these individually.
      </p>

      <Card>
        <Eyebrow>AI routing by task</Eyebrow>
        <div className="mt-4 flex flex-col gap-4">
          {Object.entries(s.ai_routes).map(([task, r]) => (
            <div key={task} className="grid grid-cols-[9rem_10rem_1fr] gap-3 items-start border-b border-line pb-3 last:border-0">
              <div>
                <div className="text-sm font-semibold capitalize">{task}</div>
                <div className="text-[11px] text-ink-2 mt-0.5">{TASK_HELP[task]}</div>
              </div>
              <div>
                <select
                  className="w-full bg-paper border border-line px-2 py-1.5 text-sm"
                  value={r.provider}
                  onChange={(e) => set(task, "provider", e.target.value)}
                >
                  {s.providers.map((p) => (
                    <option key={p} value={p}>{p === "local" ? "local (BETA)" : p}</option>
                  ))}
                </select>
                {r.provider === "local" && (
                  <div className="mono text-[10px] text-reg mt-1">BETA — no token cost, slower, lower quality</div>
                )}
              </div>
              <input
                className="w-full bg-paper border border-line px-2 py-1.5 text-sm mono"
                value={r.model}
                onChange={(e) => set(task, "model", e.target.value)}
                placeholder={r.default_model}
              />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-3 mt-5">
          <Button onClick={save}>Save routing</Button>
          {saved && <span className="text-ok text-sm">Saved</span>}
        </div>
      </Card>

      <Card className="mt-6">
        <Eyebrow>Rendering &amp; storage</Eyebrow>
        <div className="mono text-xs text-ink-2 mt-3 leading-relaxed">
          data root · {s.data_root}
          <br />
          chunked rendering engages above {s.chunk_threshold_mb} MB payload
          <br />
          budget alert at ${s.budget_alert_usd} per project
        </div>
        <p className="text-[11px] text-ink-2 mt-3">
          Thresholds are tunable via environment (PBG_CHUNK_THRESHOLD_MB and friends); artifact
          cleanup is on each project's page and in chat ("clean up render files").
        </p>
      </Card>
    </div>
  );
}
