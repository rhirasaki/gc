import { useEffect, useState } from "react";
import { api, Costs as CostsT, money } from "../api";
import { BarRow, Card, Eyebrow, Stat } from "../ui";

export default function Costs() {
  const [c, setC] = useState<CostsT | null>(null);
  useEffect(() => { api.costs().then(setC).catch(() => {}); }, []);
  if (!c) return <div className="text-ink-2 text-sm">Loading…</div>;

  const total = c.by_provider.reduce((s, r) => s + r.cost_usd, 0);
  const calls = c.by_provider.reduce((s, r) => s + r.calls, 0);
  const tokens = c.by_provider.reduce((s, r) => s + r.tokens, 0);
  const maxDay = Math.max(...c.daily.map((d) => d.cost_usd), 0.0001);
  const fmt = (v: number) => money(v);

  return (
    <div>
      <Eyebrow>Cost of goods</Eyebrow>
      <h1 className="display text-4xl mb-2">Token spend</h1>
      <p className="text-sm text-ink-2 mb-8 max-w-2xl">
        Every AI call is metered. This is what each book costs to make — margin is the business.
      </p>

      <Card className="mb-6">
        <div className="grid grid-cols-4 gap-6">
          <Stat label="Total spend" value={money(total)} />
          <Stat label="AI calls" value={calls.toLocaleString()} />
          <Stat label="Tokens" value={tokens.toLocaleString()} />
          <Stat label="Cache hits" value={c.cache_hits.toLocaleString()} sub="re-classifications avoided" />
        </div>
        {total > c.budget_alert_usd && (
          <p className="text-xs text-reg mt-4 border-t border-line pt-3">
            Spend has passed the {money(c.budget_alert_usd)} budget alert. Review provider routing before the next narrative pass.
          </p>
        )}
      </Card>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <Eyebrow>By task</Eyebrow>
          <div className="mt-3">
            {c.by_task.map((r) => (
              <BarRow key={r.key} label={r.key} value={r.cost_usd} max={Math.max(...c.by_task.map((x) => x.cost_usd), 0.0001)} format={fmt} />
            ))}
            {c.by_task.length === 0 && <div className="text-xs text-ink-2">No AI calls yet.</div>}
          </div>
        </Card>
        <Card>
          <Eyebrow>By provider</Eyebrow>
          <div className="mt-3">
            {c.by_provider.map((r) => (
              <BarRow key={r.key} label={r.key} value={r.cost_usd} max={Math.max(...c.by_provider.map((x) => x.cost_usd), 0.0001)} format={fmt} />
            ))}
            {c.by_provider.length === 0 && <div className="text-xs text-ink-2">No AI calls yet.</div>}
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        <Eyebrow>Daily trend</Eyebrow>
        {c.daily.length === 0 ? (
          <div className="text-xs text-ink-2 mt-3">Nothing metered yet.</div>
        ) : (
          <div className="flex items-end gap-1 mt-4">
            {c.daily.map((d) => (
              <div key={d.date} className="flex-1 flex flex-col items-center justify-end gap-1 h-32" title={`${d.date}: ${money(d.cost_usd)}`}>
                <div className="w-full bg-press" style={{ height: `${Math.max(3, (d.cost_usd / maxDay) * 112)}px`, borderRadius: "2px 2px 0 0" }} />
                <div className="mono text-[9px] text-ink-2">{d.date.slice(5)}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="mt-6">
        <Eyebrow>By project</Eyebrow>
        <div className="mt-3">
          {c.by_project.map((r) => (
            <BarRow key={r.key} label={r.key?.slice(0, 12) ?? "—"} value={r.cost_usd} max={Math.max(...c.by_project.map((x) => x.cost_usd), 0.0001)} format={fmt} />
          ))}
          {c.by_project.length === 0 && <div className="text-xs text-ink-2">No AI calls yet.</div>}
        </div>
      </Card>
    </div>
  );
}
