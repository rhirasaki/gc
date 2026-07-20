/** Thin typed client over the FastAPI backend. */

export type ProjectCard = {
  id: string;
  trip_name: string;
  client: string | null;
  destinations: string[];
  status: string;
  trip_reason: string | null;
  date_start: string | null;
  date_end: string | null;
  template_id: string | null;
  synopsis: string | null;
  photo_count: number;
  chapter_count: number;
  ai_spend_usd: number;
  sale_price_usd: number;
  margin_pct: number | null;
};

export type ChapterInfo = {
  id: string;
  position: number;
  label: string;
  narrative: string | null;
  dirty: boolean;
  page_start: number | null;
  page_end: number | null;
  grounding: {
    ungrounded_count?: number;
    summary?: string;
    sentences?: { text: string; verdict: string; reason?: string }[];
  } | null;
  pinned_hero: string | null;
  assets: { id: string; position: number; caption: string | null }[];
};

export type ProjectDetail = ProjectCard & {
  chapters: ChapterInfo[];
  ai_overrides: Record<string, { provider?: string; model?: string }> | null;
};

export type AssetInfo = {
  id: string;
  aspect: string | null;
  taken_at: string | null;
  finalized: boolean;
  duplicate_of: string | null;
  classification: Record<string, unknown> | null;
  role: string;
  manual_override: boolean;
  blur_score: number | null;
};

export type TemplateInfo = {
  id: string;
  name: string;
  description: string;
  builtin: boolean;
};

export type JobInfo = {
  id: string;
  kind: string;
  status: string;
  progress: number;
  note: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
};

export type Costs = {
  by_project: { key: string; cost_usd: number; tokens: number; calls: number }[];
  by_task: { key: string; cost_usd: number; tokens: number; calls: number }[];
  by_provider: { key: string; cost_usd: number; tokens: number; calls: number }[];
  daily: { date: string; cost_usd: number }[];
  cache_hits: number;
  budget_alert_usd: number;
};

export type PickCandidate = { id: string; aspect: string | null; subjects: string[] };

export type ChatReply =
  | { kind: "answer"; text: string }
  | { kind: "clarify"; question: string; options: string[] }
  | { kind: "done"; tool: string; result: Record<string, unknown>; confirmation: string }
  | { kind: "queued"; tool: string; job_id: string; confirmation: string }
  | { kind: "pick"; chapter_id: string; position: number; prompt: string; candidates: PickCandidate[] }
  | { kind: "error"; text: string };

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail ?? res.statusText);
  return res.json();
}

export const api = {
  projects: () => j<ProjectCard[]>("/api/projects"),
  project: (id: string) => j<ProjectDetail>(`/api/projects/${id}`),
  createClient: (body: object) => j<{ id: string }>("/api/clients", { method: "POST", body: JSON.stringify(body) }),
  clients: () => j<{ id: string; name: string }[]>("/api/clients"),
  createProject: (body: object) => j<{ id: string }>("/api/projects", { method: "POST", body: JSON.stringify(body) }),
  assets: (id: string) => j<AssetInfo[]>(`/api/projects/${id}/assets`),
  templates: () => j<TemplateInfo[]>("/api/templates"),
  costs: () => j<Costs>("/api/costs"),
  job: (id: string) => j<JobInfo>(`/api/jobs/${id}`),
  projectJobs: (id: string) => j<JobInfo[]>(`/api/projects/${id}/jobs`),
  chat: (id: string, message: string) =>
    j<ChatReply>(`/api/projects/${id}/chat`, { method: "POST", body: JSON.stringify({ message }) }),
  render: (id: string, tier: "preview" | "final") =>
    j<{ job_id: string }>(`/api/projects/${id}/render/${tier}`, { method: "POST" }),
  classify: (id: string) => j<{ job_id: string }>(`/api/projects/${id}/classify`, { method: "POST" }),
  finalize: (id: string) => j<{ job_id: string }>(`/api/projects/${id}/finalize-images`, { method: "POST" }),
  cleanup: (id: string) => j<{ job_id: string }>(`/api/projects/${id}/cleanup`, { method: "POST" }),
  importPhotos: (id: string) => j<object>(`/api/projects/${id}/import/photos`, { method: "POST" }),
  importNotes: (id: string, pasted: string) =>
    j<object>(`/api/projects/${id}/import/notes`, { method: "POST", body: JSON.stringify({ pasted, file_paths: [] }) }),
  proposeChapters: (id: string) => j<object>(`/api/projects/${id}/chapters/propose`, { method: "POST" }),
  narrative: (id: string, chapter_id: string, tone?: string) =>
    j<{ job_id: string }>(`/api/projects/${id}/narrative`, {
      method: "POST",
      body: JSON.stringify({ chapter_id, tone, word_count: 350 }),
    }),
  renameChapter: (id: string, chapterId: string, label: string) =>
    j<object>(`/api/projects/${id}/chapters/${chapterId}/rename`, { method: "POST", body: JSON.stringify({ label }) }),
  pinHero: (id: string, chapterId: string, asset_id: string | null) =>
    j<object>(`/api/projects/${id}/chapters/${chapterId}/pin-hero`, { method: "POST", body: JSON.stringify({ asset_id }) }),
  addChapterAsset: (id: string, chapterId: string, asset_id: string) =>
    j<object>(`/api/projects/${id}/chapters/${chapterId}/assets`, { method: "POST", body: JSON.stringify({ asset_id }) }),
  removeChapterAsset: (id: string, chapterId: string, position: number) =>
    j<object>(`/api/projects/${id}/chapters/${chapterId}/assets/${position}`, { method: "DELETE" }),
  reorderChapter: (id: string, chapterId: string, order: string[]) =>
    j<object>(`/api/projects/${id}/chapters/${chapterId}/reorder`, { method: "POST", body: JSON.stringify({ order }) }),
  swap: (id: string, chapter_id: string, position: number, new_asset_id: string) =>
    j<{ swapped: boolean; chapter: string }>(`/api/projects/${id}/swap`, {
      method: "POST",
      body: JSON.stringify({ chapter_id, position, new_asset_id }),
    }),
  synopsis: (id: string) => j<{ synopsis: string }>(`/api/projects/${id}/synopsis`, { method: "POST" }),
  undo: (id: string) => j<{ undone: boolean; undid?: string; reason?: string }>(`/api/projects/${id}/undo`, { method: "POST" }),
  changes: (id: string) => j<{ tool: string; args: Record<string, unknown>; source: string; at: string }[]>(`/api/projects/${id}/changes`),
  setAiOverrides: (id: string, ai_overrides: object) =>
    j<object>(`/api/projects/${id}/ai-overrides`, { method: "POST", body: JSON.stringify({ ai_overrides }) }),
  uploadFiles: (id: string, kind: "notes" | "pins", files: FileList) => {
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    return fetch(`/api/projects/${id}/upload/${kind}`, { method: "POST", body: form }).then(async (r) => {
      if (!r.ok) throw new Error((await r.json().catch(() => ({})))?.detail ?? r.statusText);
      return r.json() as Promise<{ imported: number }>;
    });
  },
  overrideAsset: (assetId: string, body: object) =>
    j<object>(`/api/assets/${assetId}/override`, { method: "POST", body: JSON.stringify(body) }),
  saveTemplate: (body: object) => j<{ id: string }>("/api/templates", { method: "POST", body: JSON.stringify(body) }),
};

export const money = (v: number) =>
  v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: v < 10 ? 2 : 0 });
