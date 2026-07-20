import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, AssetInfo, ChapterInfo, ChatReply, JobInfo, money, ProjectDetail } from "../api";
import { Button, Card, Eyebrow, Progress, Stat, StatusTag } from "../ui";

type Tab = "book" | "photos" | "chat" | "sources" | "history";

export default function Project() {
  const { id = "" } = useParams();
  const [p, setP] = useState<ProjectDetail | null>(null);
  const [assets, setAssets] = useState<AssetInfo[]>([]);
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [tab, setTab] = useState<Tab>("book");
  const [toast, setToast] = useState<string | null>(null);

  const reload = useCallback(() => {
    api.project(id).then(setP).catch(() => {});
    api.assets(id).then(setAssets).catch(() => {});
    api.projectJobs(id).then(setJobs).catch(() => {});
  }, [id]);

  useEffect(reload, [reload]);
  // Live progress while any job runs.
  useEffect(() => {
    if (!jobs.some((j) => j.status === "running" || j.status === "queued")) return;
    const t = setInterval(reload, 2500);
    return () => clearInterval(t);
  }, [jobs, reload]);

  if (!p) return <div className="text-ink-2 text-sm">Loading…</div>;
  const say = (m: string) => { setToast(m); setTimeout(() => setToast(null), 4000); };
  const kick = (fn: () => Promise<unknown>, m: string) => () => fn().then(() => { say(m); reload(); }).catch((e) => say(String(e)));

  const active = jobs.filter((j) => j.status === "running" || j.status === "queued");

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <Eyebrow>{p.client} · {p.destinations?.join(", ")}</Eyebrow>
          <h1 className="display text-4xl">{p.trip_name}</h1>
        </div>
        <StatusTag status={p.status} />
      </div>

      <Card className="mb-6">
        <div className="grid grid-cols-5 gap-6">
          <Stat label="Photos" value={p.photo_count} />
          <Stat label="Chapters" value={p.chapter_count} />
          <Stat label="AI spend" value={money(p.ai_spend_usd)} sub={`of ${money(p.sale_price_usd)} sale`} />
          <Stat label="Margin" value={p.margin_pct != null ? `${p.margin_pct}%` : "—"} />
          <Stat label="Template" value={<span className="text-sm">{p.template_id}</span>} />
        </div>
        {p.synopsis && <p className="text-sm text-ink-2 mt-4 border-t border-line pt-3">{p.synopsis}</p>}
      </Card>

      {active.map((j) => (
        <Card key={j.id} className="mb-4">
          <div className="flex justify-between mb-2">
            <span className="mono text-xs">{j.kind}</span>
            <span className="mono text-xs text-ink-2">{Math.round(j.progress * 100)}%</span>
          </div>
          <Progress value={j.progress} note={j.note} />
        </Card>
      ))}

      <div className="flex gap-2 mb-4 flex-wrap">
        <Button kind="quiet" onClick={kick(() => api.importPhotos(id), "Photos imported")}>Import photos</Button>
        <Button kind="quiet" onClick={kick(() => api.proposeChapters(id), "Chapters proposed from photo days")}>Propose chapters</Button>
        <Button kind="quiet" onClick={kick(() => api.classify(id), "Classification queued")}>Classify photos</Button>
        <Button kind="quiet" onClick={kick(() => api.render(id, "preview"), "Preview render queued")}>Render preview</Button>
        <Button onClick={kick(() => api.render(id, "final"), "Final render queued")}>Render final</Button>
        <Button kind="quiet" onClick={kick(() => api.finalize(id), "High-res finalize queued")}>Finalize images</Button>
        <a className="px-3.5 py-1.5 text-sm font-medium border border-line hover:border-ink" href={`/api/projects/${id}/book/web`} target="_blank" rel="noreferrer">Open web preview</a>
        <a className="px-3.5 py-1.5 text-sm font-medium border border-line hover:border-ink" href={`/api/projects/${id}/book/preview`} target="_blank" rel="noreferrer">Open preview PDF</a>
        <a className="px-3.5 py-1.5 text-sm font-medium border border-line hover:border-ink" href={`/api/projects/${id}/book/final`} target="_blank" rel="noreferrer">Open final PDF</a>
      </div>

      <div className="flex gap-0 border-b border-line mb-5">
        {(["book", "photos", "chat", "sources", "history"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize border-b-2 -mb-px ${tab === t ? "border-press text-press font-semibold" : "border-transparent text-ink-2"}`}>
            {t === "book" ? "Chapters" : t}
          </button>
        ))}
      </div>

      {tab === "book" && (
        <Chapters p={p} projectId={id} assets={assets} say={say} reload={reload}
          onNarrative={(cid) => kick(() => api.narrative(id, cid), "Narrative generation queued")()} />
      )}
      {tab === "photos" && <Photos assets={assets} onOverride={(aid, role) => api.overrideAsset(aid, { role }).then(reload)} />}
      {tab === "chat" && <Chat id={id} onChanged={reload} />}
      {tab === "sources" && <Sources id={id} p={p} say={say} reload={reload} />}
      {tab === "history" && <History id={id} say={say} reload={reload} />}

      {toast && (
        <div className="fixed bottom-6 right-6 bg-ink text-paper px-4 py-2 text-sm shadow-lg">{toast}</div>
      )}
    </div>
  );
}

function Chapters({ p, projectId, assets, say, reload, onNarrative }: {
  p: ProjectDetail;
  projectId: string;
  assets: AssetInfo[];
  say: (m: string) => void;
  reload: () => void;
  onNarrative: (chapterId: string) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  if (p.chapters.length === 0)
    return <Card className="text-sm text-ink-2">No chapters yet. Import photos, then propose chapters — days are clustered from EXIF timestamps.</Card>;
  return (
    <div className="flex flex-col gap-4">
      {p.chapters.map((c) => {
        const ungrounded = c.grounding?.ungrounded_count ?? 0;
        return (
          <Card key={c.id}>
            <div className="flex items-start justify-between">
              <div>
                <Eyebrow>Chapter {c.position + 1}{c.page_start ? ` · pp. ${c.page_start}–${c.page_end}` : ""}</Eyebrow>
                <div className="display text-xl">{c.label}</div>
              </div>
              <div className="flex items-center gap-2">
                {c.dirty && <span className="mono text-[10px] text-press border border-press/40 px-2 py-0.5">CHANGED</span>}
                {ungrounded > 0 && (
                  <span className="mono text-[10px] text-reg border border-reg/40 px-2 py-0.5" title={c.grounding?.summary}>
                    {ungrounded} UNGROUNDED
                  </span>
                )}
                <Button kind="quiet" onClick={() => onNarrative(c.id)}>
                  {c.narrative ? "Rewrite narrative" : "Write narrative"}
                </Button>
                <Button kind="quiet" onClick={() => setOpen(open === c.id ? null : c.id)}>
                  {open === c.id ? "Close" : "Edit"}
                </Button>
              </div>
            </div>
            <div className="mono text-xs text-ink-2 mt-2">{c.assets.length} photos</div>
            {c.narrative && <p className="text-sm mt-3 line-clamp-3 max-w-3xl">{c.narrative}</p>}
            {ungrounded > 0 && c.grounding?.summary && (
              <p className="text-xs text-reg mt-2">{c.grounding.summary}</p>
            )}
            {open === c.id && (
              <ChapterEditor projectId={projectId} chapter={c} assets={assets} say={say} reload={reload} />
            )}
          </Card>
        );
      })}
    </div>
  );
}

function ChapterEditor({ projectId, chapter, assets, say, reload }: {
  projectId: string;
  chapter: ChapterInfo;
  assets: AssetInfo[];
  say: (m: string) => void;
  reload: () => void;
}) {
  const [label, setLabel] = useState(chapter.label);
  const [adding, setAdding] = useState(false);
  const inChapter = new Set(chapter.assets.map((a) => a.id));
  const library = assets.filter((a) => !a.duplicate_of && !inChapter.has(a.id));
  const run = (fn: Promise<unknown>, m: string) =>
    fn.then(() => { say(m); reload(); }).catch((e) => say(String(e)));

  const move = (from: number, dir: -1 | 1) => {
    const order = [...chapter.assets].sort((a, b) => a.position - b.position).map((a) => a.id);
    const to = from + dir;
    if (to < 0 || to >= order.length) return;
    [order[from], order[to]] = [order[to], order[from]];
    run(api.reorderChapter(projectId, chapter.id, order), "Reordered");
  };

  return (
    <div className="border-t border-line mt-4 pt-4">
      <div className="flex gap-2 items-center mb-4">
        <input className="bg-paper border border-line px-3 py-1.5 text-sm flex-1 max-w-sm"
          value={label} onChange={(e) => setLabel(e.target.value)} />
        <Button kind="quiet" disabled={label === chapter.label || !label.trim()}
          onClick={() => run(api.renameChapter(projectId, chapter.id, label.trim()), "Renamed")}>
          Rename
        </Button>
      </div>

      <div className="flex gap-2 flex-wrap">
        {[...chapter.assets].sort((a, b) => a.position - b.position).map((a, i) => (
          <div key={a.id} className="w-28">
            <div className={`relative border ${chapter.pinned_hero === a.id ? "border-press border-2" : "border-line"}`}>
              <img src={`/api/assets/${a.id}/file`} alt="" className="w-full h-20 object-cover" loading="lazy" />
              {chapter.pinned_hero === a.id && (
                <span className="absolute top-0 left-0 mono text-[9px] bg-press text-white px-1">HERO</span>
              )}
            </div>
            <div className="flex justify-between mt-1">
              <button className="mono text-xs px-1 hover:text-press disabled:opacity-30" disabled={i === 0}
                onClick={() => move(i, -1)} title="Move earlier">←</button>
              <button className="mono text-[10px] px-1 hover:text-press"
                title={chapter.pinned_hero === a.id ? "Unpin hero" : "Pin as chapter hero — auto-selection won't override this"}
                onClick={() => run(api.pinHero(projectId, chapter.id, chapter.pinned_hero === a.id ? null : a.id),
                  chapter.pinned_hero === a.id ? "Hero unpinned" : "Hero pinned")}>
                {chapter.pinned_hero === a.id ? "unpin" : "pin"}
              </button>
              <button className="mono text-xs px-1 hover:text-reg" title="Remove from chapter"
                onClick={() => run(api.removeChapterAsset(projectId, chapter.id, a.position), "Photo removed")}>×</button>
              <button className="mono text-xs px-1 hover:text-press disabled:opacity-30" disabled={i === chapter.assets.length - 1}
                onClick={() => move(i, 1)} title="Move later">→</button>
            </div>
          </div>
        ))}
        <button className="w-28 h-20 border border-dashed border-line hover:border-press text-ink-2 text-2xl"
          title="Add a photo from the library" onClick={() => setAdding(!adding)}>+</button>
      </div>

      {adding && (
        <div className="mt-3 border border-line p-3 bg-paper">
          <Eyebrow>Add from library</Eyebrow>
          {library.length === 0 ? (
            <div className="text-xs text-ink-2 mt-2">Every photo is already placed.</div>
          ) : (
            <div className="grid grid-cols-8 gap-2 mt-2 max-h-48 overflow-y-auto">
              {library.map((a) => (
                <button key={a.id} className="border border-line hover:border-press p-0"
                  title={(a.classification?.subjects as string[])?.join(", ") ?? a.aspect ?? ""}
                  onClick={() => { setAdding(false); run(api.addChapterAsset(projectId, chapter.id, a.id), "Photo added"); }}>
                  <img src={`/api/assets/${a.id}/file`} alt="" className="w-full h-16 object-cover" loading="lazy" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {!!chapter.grounding?.sentences?.length && (
        <div className="mt-4">
          <Eyebrow>Grounding review</Eyebrow>
          <div className="mt-2 flex flex-col gap-1">
            {chapter.grounding.sentences.map((s, i) => (
              <div key={i} className="flex gap-2 items-baseline text-xs">
                <span className={`mono text-[9px] uppercase w-20 shrink-0 ${
                  s.verdict === "ungrounded" ? "text-reg" : s.verdict === "context" ? "text-press" : "text-ok"}`}>
                  {s.verdict}
                </span>
                <span className={s.verdict === "ungrounded" ? "text-reg" : "text-ink-2"}>
                  {s.text}{s.reason && s.verdict === "ungrounded" ? ` — ${s.reason}` : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Photos({ assets, onOverride }: { assets: AssetInfo[]; onOverride: (id: string, role: string) => void }) {
  const live = assets.filter((a) => !a.duplicate_of);
  if (live.length === 0) return <Card className="text-sm text-ink-2">No photos yet. Set the project's photo folder and import.</Card>;
  return (
    <div className="grid grid-cols-4 gap-4">
      {live.map((a) => (
        <Card key={a.id} className="p-0 overflow-hidden">
          <img src={`/api/assets/${a.id}/file`} alt="" className="w-full h-40 object-cover" loading="lazy" />
          <div className="p-3">
            <div className="mono text-[10px] text-ink-2 flex justify-between">
              <span>{a.aspect ?? "?"}</span>
              <span>{a.finalized ? "HI-RES" : "draft"}</span>
            </div>
            {a.classification ? (
              <div className="text-xs mt-1 line-clamp-1">{(a.classification.subjects as string[])?.join(", ")}</div>
            ) : (
              <div className="text-xs text-ink-2 mt-1">unclassified</div>
            )}
            <select
              className="mt-2 w-full bg-paper border border-line text-xs px-1 py-1"
              value={a.role}
              onChange={(e) => onOverride(a.id, e.target.value)}
              title={a.manual_override ? "Manually set — re-classification will not change this" : "Suggested by classification"}
            >
              {["hero", "detail", "candid", "unassigned"].map((r) => <option key={r}>{r}</option>)}
            </select>
          </div>
        </Card>
      ))}
    </div>
  );
}

const TASKS = ["classification", "narrative", "research", "chat", "grounding", "synopsis"];
const PROVIDERS = ["", "anthropic", "google", "deepseek", "openai", "local"];

function Sources({ id, p, say, reload }: { id: string; p: ProjectDetail; say: (m: string) => void; reload: () => void }) {
  const [pasted, setPasted] = useState("");
  const [ov, setOv] = useState<Record<string, { provider?: string; model?: string }>>(p.ai_overrides ?? {});
  const [folderId, setFolderId] = useState(p.drive_folder_id ?? "");
  const [conn, setConn] = useState<{ drive_connected: boolean; places_connected: boolean } | null>(null);
  useEffect(() => { api.connections().then(setConn).catch(() => {}); }, []);

  const upload = (kind: "notes" | "pins") => (e: { target: HTMLInputElement }) => {
    if (!e.target.files?.length) return;
    api.uploadFiles(id, kind, e.target.files)
      .then((r) => { say(`Imported ${r.imported} ${kind}`); reload(); })
      .catch((err) => say(String(err)));
    e.target.value = "";
  };

  return (
    <div className="grid grid-cols-2 gap-6">
      <Card>
        <Eyebrow>Trip notes</Eyebrow>
        <p className="text-xs text-ink-2 mt-2">
          Apple Notes exports (.html), Google Keep (.json), Word (.docx), or plain text — or paste below.
        </p>
        <input type="file" multiple accept=".html,.htm,.json,.docx,.txt,.md"
          className="mt-3 text-xs" onChange={upload("notes")} />
        <textarea
          className="w-full bg-paper border border-line px-3 py-2 text-sm mt-3 h-28"
          placeholder="Paste notes here…"
          value={pasted}
          onChange={(e) => setPasted(e.target.value)}
        />
        <div className="mt-2">
          <Button kind="quiet" disabled={!pasted.trim()}
            onClick={() => api.importNotes(id, pasted).then(() => { setPasted(""); say("Notes imported"); reload(); })}>
            Import pasted notes
          </Button>
        </div>
      </Card>

      <Card>
        <Eyebrow>Map pins</Eyebrow>
        <p className="text-xs text-ink-2 mt-2">
          Google Takeout "Saved Places" — KML or GeoJSON.
        </p>
        <input type="file" multiple accept=".kml,.geojson,.json"
          className="mt-3 text-xs" onChange={upload("pins")} />
        <div className="mt-3">
          <Button kind="quiet" disabled={!conn?.places_connected}
            onClick={() => api.enrichPins(id).then((r) => { say(`Enrichment queued (job ${r.job_id.slice(0, 8)})`); reload(); }).catch((e) => say(String(e)))}>
            Enrich pins via Places
          </Button>
          {conn && !conn.places_connected && (
            <div className="mono text-[10px] text-ink-2 mt-1">
              Needs GOOGLE_MAPS_API_KEY — fills in categories and exact coordinates.
            </div>
          )}
        </div>

        <div className="border-t border-line mt-5 pt-4">
          <Eyebrow>Synopsis</Eyebrow>
          <p className="text-xs text-ink-2 mt-2">{p.synopsis ?? "No synopsis yet."}</p>
          <div className="mt-2">
            <Button kind="quiet" onClick={() => api.synopsis(id).then(() => { say("Synopsis updated"); reload(); }).catch((e) => say(String(e)))}>
              {p.synopsis ? "Rewrite synopsis" : "Write synopsis"}
            </Button>
          </div>
        </div>
      </Card>

      <Card className="col-span-2">
        <Eyebrow>Google Drive</Eyebrow>
        <p className="text-xs text-ink-2 mt-2">
          Optional sync: pull the client's photos, notes and map exports from a shared Drive
          folder; push rendered PDFs back to a "Rendered" subfolder. Local folders remain the
          source of truth.
        </p>
        <div className="flex gap-2 items-center mt-3">
          <input className="bg-paper border border-line px-3 py-1.5 text-sm mono flex-1 max-w-md"
            placeholder="Drive folder id (from the folder's URL)"
            value={folderId} onChange={(e) => setFolderId(e.target.value)} />
          <Button kind="quiet" disabled={folderId === (p.drive_folder_id ?? "")}
            onClick={() => api.driveConfig(id, folderId.trim() || null).then(() => { say("Drive folder saved"); reload(); })}>
            Save folder
          </Button>
          <Button kind="quiet" disabled={!conn?.drive_connected || !p.drive_folder_id}
            onClick={() => api.driveSync(id, "pull").then((r) => say(`Drive pull queued (job ${r.job_id.slice(0, 8)})`)).catch((e) => say(String(e)))}>
            Pull from Drive
          </Button>
          <Button kind="quiet" disabled={!conn?.drive_connected || !p.drive_folder_id}
            onClick={() => api.driveSync(id, "push").then((r) => say(`Drive push queued (job ${r.job_id.slice(0, 8)})`)).catch((e) => say(String(e)))}>
            Push renders
          </Button>
        </div>
        {conn && !conn.drive_connected && (
          <div className="mono text-[10px] text-ink-2 mt-2">
            Not connected — set PBG_GDRIVE_CLIENT_ID / PBG_GDRIVE_CLIENT_SECRET / PBG_GDRIVE_REFRESH_TOKEN and restart the backend.
          </div>
        )}
      </Card>

      <Card className="col-span-2">
        <Eyebrow>Model routing for this commission</Eyebrow>
        <p className="text-xs text-ink-2 mt-2 mb-3">
          Leave blank to use the studio defaults from Settings.
        </p>
        <div className="grid grid-cols-3 gap-3">
          {TASKS.map((t) => (
            <div key={t} className="flex items-center gap-2">
              <span className="text-xs w-24 capitalize">{t}</span>
              <select
                className="flex-1 bg-paper border border-line px-2 py-1 text-xs"
                value={ov[t]?.provider ?? ""}
                onChange={(e) => {
                  const next = { ...ov };
                  if (e.target.value) next[t] = { ...next[t], provider: e.target.value };
                  else delete next[t];
                  setOv(next);
                }}
              >
                {PROVIDERS.map((pr) => (
                  <option key={pr} value={pr}>{pr === "" ? "default" : pr === "local" ? "local (BETA)" : pr}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <Button onClick={() => api.setAiOverrides(id, ov).then(() => say("Routing saved")).catch((e) => say(String(e)))}>
            Save routing
          </Button>
        </div>
      </Card>
    </div>
  );
}

function History({ id, say, reload }: { id: string; say: (m: string) => void; reload: () => void }) {
  const [rows, setRows] = useState<{ tool: string; args: Record<string, unknown>; source: string; at: string }[]>([]);
  const load = useCallback(() => { api.changes(id).then(setRows).catch(() => {}); }, [id]);
  useEffect(load, [load]);

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <Eyebrow>Change log</Eyebrow>
        <Button kind="quiet" onClick={() =>
          api.undo(id).then((r) => { say(r.undone ? `Undid ${r.undid}` : r.reason ?? "Nothing to undo"); load(); reload(); })}>
          Undo last change
        </Button>
      </div>
      {rows.length === 0 && <div className="text-xs text-ink-2">No changes yet — edits from chat and the UI land here.</div>}
      <div className="flex flex-col">
        {rows.map((r, i) => (
          <div key={i} className="grid grid-cols-[10rem_1fr_4rem_10rem] gap-3 items-baseline border-b border-line last:border-0 py-2">
            <span className="mono text-xs">{r.tool}</span>
            <span className="text-xs text-ink-2 truncate">{JSON.stringify(r.args)}</span>
            <span className="mono text-[10px] uppercase text-ink-2">{r.source}</span>
            <span className="mono text-[10px] text-ink-2 text-right">{new Date(r.at).toLocaleString()}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

type ChatMsg = {
  who: "you" | "studio";
  text: string;
  pick?: { chapter_id: string; position: number; candidates: import("../api").PickCandidate[] };
};

function Chat({ id, onChanged }: { id: string; onChanged: () => void }) {
  const [log, setLog] = useState<ChatMsg[]>([
    { who: "studio", text: "Tell me what to change — “swap the third photo in the Vik chapter for a wider shot”, “make chapter 2 warmer”, “render a preview”." },
  ]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [log]);

  async function send() {
    if (!msg.trim() || busy) return;
    const text = msg.trim();
    setLog((l) => [...l, { who: "you", text }]);
    setMsg("");
    setBusy(true);
    try {
      const r: ChatReply = await api.chat(id, text);
      if (r.kind === "pick") {
        setLog((l) => [...l, {
          who: "studio", text: r.prompt,
          pick: { chapter_id: r.chapter_id, position: r.position, candidates: r.candidates },
        }]);
      } else {
        const reply =
          r.kind === "answer" ? r.text
          : r.kind === "clarify" ? `${r.question}${r.options?.length ? ` (${r.options.join(" / ")})` : ""}`
          : r.kind === "done" ? r.confirmation || "Done."
          : r.kind === "queued" ? `${r.confirmation || "Queued."} (job ${r.job_id.slice(0, 8)})`
          : r.text;
        setLog((l) => [...l, { who: "studio", text: reply }]);
        if (r.kind === "done" || r.kind === "queued") onChanged();
      }
    } catch (e) {
      setLog((l) => [...l, { who: "studio", text: `That didn't work: ${e}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col h-[28rem]">
      <div className="flex-1 overflow-y-auto flex flex-col gap-3 pr-2">
        {log.map((m, i) => (
          <div key={i} className={`max-w-[80%] text-sm px-3 py-2 ${m.who === "you" ? "self-end bg-press text-white" : "self-start bg-paper border border-line"}`}>
            {m.text}
            {m.pick && (
              <div className="grid grid-cols-4 gap-2 mt-2">
                {m.pick.candidates.map((c) => (
                  <button key={c.id} title={c.subjects?.join(", ") || c.aspect || ""}
                    className="border border-line hover:border-press p-0 bg-transparent cursor-pointer"
                    onClick={() =>
                      api.swap(id, m.pick!.chapter_id, m.pick!.position, c.id)
                        .then((r) => {
                          setLog((l) => [...l, { who: "studio", text: `Swapped into “${r.chapter}”.` }]);
                          onChanged();
                        })
                        .catch((e) => setLog((l) => [...l, { who: "studio", text: String(e) }]))}>
                    <img src={`/api/assets/${c.id}/file`} alt={c.subjects?.join(", ") || "candidate"} className="w-full h-16 object-cover" />
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={end} />
      </div>
      <div className="flex gap-2 mt-3 border-t border-line pt-3">
        <input
          className="flex-1 bg-paper border border-line px-3 py-2 text-sm"
          placeholder="Ask for a change…"
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <Button onClick={send} disabled={busy}>{busy ? "…" : "Send"}</Button>
      </div>
    </Card>
  );
}
