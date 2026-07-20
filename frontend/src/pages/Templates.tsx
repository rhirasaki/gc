import { useEffect, useState } from "react";
import { api, TemplateInfo } from "../api";
import { Button, Card, Eyebrow } from "../ui";

/** Swatch strips per builtin so the gallery reads as design, not a list. */
const PALETTES: Record<string, string[]> = {
  "heritage-journal": ["#f7f2e9", "#9a7b3f", "#5c6b4c", "#2d2419"],
  "modern-editorial": ["#ffffff", "#0d0d0d", "#e63312"],
  "scandinavian-minimal": ["#fafaf7", "#c9c5bb", "#8a8578", "#3c3a36"],
  "coastal-tropical": ["#fffdf8", "#0e8ba8", "#f2a03d", "#17383e"],
  "leather-archive": ["#f5efe4", "#6b1f2a", "#8c6d3f", "#241a16"],
  "alpine-adventure": ["#f4f5f2", "#c75b12", "#38505a", "#23282b"],
};

export default function Templates() {
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [cloning, setCloning] = useState<TemplateInfo | null>(null);

  const load = () => api.templates().then(setTemplates).catch(() => {});
  useEffect(() => { load(); }, []);

  return (
    <div>
      <Eyebrow>Library</Eyebrow>
      <h1 className="display text-4xl mb-2">Templates</h1>
      <p className="text-sm text-ink-2 mb-8 max-w-2xl">
        Six house styles, each a token bundle over shared layout logic. Clone one, adjust its
        tokens, and the copy is available to every project.
      </p>
      <div className="grid grid-cols-3 gap-6">
        {templates.map((t) => (
          <Card key={t.id}>
            <div className="flex h-8 mb-3">
              {(PALETTES[t.id] ?? ["#ddd", "#aaa", "#666"]).map((c) => (
                <div key={c} className="flex-1" style={{ background: c }} title={c} />
              ))}
            </div>
            <div className="flex items-center justify-between">
              <div className="display text-xl">{t.name}</div>
              {!t.builtin && <span className="mono text-[10px] text-press border border-press/40 px-1.5">CUSTOM</span>}
            </div>
            <p className="text-xs text-ink-2 mt-2 min-h-[3rem]">{t.description}</p>
            <div className="mt-3">
              <Button kind="quiet" onClick={() => setCloning(t)}>Clone &amp; customize</Button>
            </div>
          </Card>
        ))}
      </div>

      {cloning && <CloneDialog base={cloning} onClose={() => { setCloning(null); load(); }} />}
    </div>
  );
}

function CloneDialog({ base, onClose }: { base: TemplateInfo; onClose: () => void }) {
  const [name, setName] = useState(`${base.name} (custom)`);
  const [accent, setAccent] = useState("#2742c0");
  const [paper, setPaper] = useState("#f7f2e9");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    await api.saveTemplate({
      id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
      name,
      description: `Custom variant of ${base.name}`,
      base_template_id: base.id,
      tokens: { "--accent": accent, "--paper": paper },
      page_config: {},
    });
    setBusy(false);
    onClose();
  }

  return (
    <div className="fixed inset-0 bg-ink/40 flex items-center justify-center" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}>
        <Card className="w-96 bg-card">
          <Eyebrow>Clone of {base.name}</Eyebrow>
          <label className="eyebrow block mt-4 mb-1">Name</label>
          <input className="w-full bg-paper border border-line px-3 py-2 text-sm" value={name} onChange={(e) => setName(e.target.value)} />
          <div className="grid grid-cols-2 gap-4 mt-4">
            <div>
              <label className="eyebrow block mb-1">Accent</label>
              <input type="color" className="w-full h-9 border border-line" value={accent} onChange={(e) => setAccent(e.target.value)} />
            </div>
            <div>
              <label className="eyebrow block mb-1">Paper</label>
              <input type="color" className="w-full h-9 border border-line" value={paper} onChange={(e) => setPaper(e.target.value)} />
            </div>
          </div>
          <div className="flex gap-2 mt-5">
            <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save template"}</Button>
            <Button kind="quiet" onClick={onClose}>Cancel</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
