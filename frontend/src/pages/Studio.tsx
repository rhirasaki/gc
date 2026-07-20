import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, money, ProjectCard } from "../api";
import { Card, Eyebrow, StatusTag } from "../ui";

export default function Studio() {
  const [projects, setProjects] = useState<ProjectCard[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.projects().then(setProjects).catch((e) => setError(String(e)));
  }, []);

  return (
    <div>
      <div className="flex items-end justify-between mb-8">
        <div>
          <Eyebrow>Commissions</Eyebrow>
          <h1 className="display text-4xl">On the press</h1>
        </div>
        <Link to="/new" className="bg-press text-white px-4 py-2 text-sm font-medium hover:bg-ink transition-colors">
          New commission
        </Link>
      </div>

      {error && <Card className="text-reg text-sm">Backend unreachable — start it with <span className="mono">uvicorn app.main:app</span>. {error}</Card>}
      {projects && projects.length === 0 && (
        <Card className="text-center py-16">
          <div className="display text-2xl mb-2">The press is quiet</div>
          <p className="text-sm text-ink-2 mb-4">Start your first commission: client, trip, photos.</p>
          <Link to="/new" className="text-press font-medium text-sm">Create a project →</Link>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-6">
        {projects?.map((p, i) => (
          <Link key={p.id} to={`/projects/${p.id}`}>
            <Card className="hover:border-ink transition-colors h-full">
              <div className="flex items-start justify-between mb-2">
                <Eyebrow>PROJ — {String(i + 1).padStart(3, "0")}</Eyebrow>
                <StatusTag status={p.status} />
              </div>
              <div className="display text-2xl leading-tight">{p.trip_name}</div>
              <div className="text-sm text-ink-2 mt-1">
                {p.client}
                {p.destinations?.length ? ` · ${p.destinations.join(", ")}` : ""}
                {p.trip_reason ? ` · ${p.trip_reason}` : ""}
              </div>
              {p.synopsis && <p className="text-sm mt-3 line-clamp-2">{p.synopsis}</p>}
              <div className="mono text-xs text-ink-2 mt-4 flex gap-5">
                <span>{p.photo_count} photos</span>
                <span>{p.chapter_count} chapters</span>
                <span>
                  spend {money(p.ai_spend_usd)} / {money(p.sale_price_usd)}
                </span>
                {p.margin_pct != null && (
                  <span className={p.margin_pct > 90 ? "text-ok" : p.margin_pct > 50 ? "text-ink" : "text-reg"}>
                    {p.margin_pct}% margin
                  </span>
                )}
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
