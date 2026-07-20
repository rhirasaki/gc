import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, TemplateInfo } from "../api";
import { Card, Eyebrow } from "../ui";

const field = "w-full bg-paper border border-line px-3 py-2 text-sm focus:border-press";
const label = "eyebrow block mb-1 mt-4";

export default function NewProject() {
  const nav = useNavigate();
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [clients, setClients] = useState<{ id: string; name: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [f, setF] = useState({
    clientName: "", clientEmail: "", clientId: "",
    trip_name: "", destinations: "", trip_reason: "",
    date_start: "", date_end: "", input_path: "",
    template_id: "heritage-journal", sale_price_usd: 2500, images_per_chapter: 10,
  });

  useEffect(() => {
    api.templates().then(setTemplates).catch(() => {});
    api.clients().then(setClients).catch(() => {});
  }, []);

  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      let clientId = f.clientId;
      if (!clientId) {
        const c = await api.createClient({ name: f.clientName, email: f.clientEmail || null });
        clientId = c.id;
      }
      const p = await api.createProject({
        client_id: clientId,
        trip_name: f.trip_name,
        destinations: f.destinations.split(",").map((s) => s.trim()).filter(Boolean),
        trip_reason: f.trip_reason || null,
        date_start: f.date_start ? new Date(f.date_start).toISOString() : null,
        date_end: f.date_end ? new Date(f.date_end).toISOString() : null,
        input_path: f.input_path || null,
        template_id: f.template_id,
        sale_price_usd: Number(f.sale_price_usd),
        images_per_chapter: Number(f.images_per_chapter),
      });
      nav(`/projects/${p.id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <Eyebrow>Intake</Eyebrow>
      <h1 className="display text-4xl mb-6">New commission</h1>
      <form onSubmit={submit}>
        <Card>
          <div className="eyebrow mb-3">Client</div>
          {clients.length > 0 && (
            <select className={field} value={f.clientId} onChange={set("clientId")}>
              <option value="">New client…</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          {!f.clientId && (
            <>
              <label className={label}>Name</label>
              <input className={field} required={!f.clientId} value={f.clientName} onChange={set("clientName")} />
              <label className={label}>Email</label>
              <input className={field} type="email" value={f.clientEmail} onChange={set("clientEmail")} />
            </>
          )}
        </Card>

        <Card className="mt-6">
          <div className="eyebrow mb-3">Trip</div>
          <label className={label}>Trip name</label>
          <input className={field} required value={f.trip_name} onChange={set("trip_name")} placeholder="Iceland, Together" />
          <label className={label}>Destinations (comma-separated)</label>
          <input className={field} value={f.destinations} onChange={set("destinations")} placeholder="Reykjavik, Vik" />
          <label className={label}>Occasion</label>
          <input className={field} value={f.trip_reason} onChange={set("trip_reason")} placeholder="25th anniversary" />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={label}>From</label>
              <input className={field} type="date" value={f.date_start} onChange={set("date_start")} />
            </div>
            <div>
              <label className={label}>To</label>
              <input className={field} type="date" value={f.date_end} onChange={set("date_end")} />
            </div>
          </div>
        </Card>

        <Card className="mt-6">
          <div className="eyebrow mb-3">Production</div>
          <label className={label}>Photo folder (local path)</label>
          <input className={field} value={f.input_path} onChange={set("input_path")} placeholder="/photos/iceland-2025" />
          <label className={label}>Template</label>
          <select className={field} value={f.template_id} onChange={set("template_id")}>
            {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={label}>Sale price (USD)</label>
              <input className={field} type="number" value={f.sale_price_usd} onChange={set("sale_price_usd")} />
            </div>
            <div>
              <label className={label}>Images per chapter</label>
              <input className={field} type="number" min={5} max={15} value={f.images_per_chapter} onChange={set("images_per_chapter")} />
            </div>
          </div>
        </Card>

        {error && <div className="text-reg text-sm mt-4">{error}</div>}
        <button disabled={busy} className="mt-6 bg-press text-white px-5 py-2.5 text-sm font-medium hover:bg-ink transition-colors disabled:opacity-40">
          {busy ? "Creating…" : "Create commission"}
        </button>
      </form>
    </div>
  );
}
