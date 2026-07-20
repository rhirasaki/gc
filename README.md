# Photo Book Generator

Ingests everything a traveler collected on a trip — notes, Google Maps pins, photos —
and produces a print-ready, richly designed PDF photo book with a grounded,
professionally written narrative. Built as a business tool: a solo operator selling
$2,000–$3,000 luxury travel books, with AI spend metered as COGS.

## Layout

```
backend/            FastAPI app
  app/
    models.py       Data model: Client/Project/Asset/Note/MapPin/Chapter/
                    Template/AIRun/ChangeLog/Job/AppSetting
    rendering/      The binding render architecture (see below)
    build/          Project -> chapter fragments -> marked monolith HTML
    layout/         Deterministic page-layout variant selection
    photos/         EXIF, derivatives, blur/phash heuristics, palette sampling
    ingestion/      Notes (Apple/Keep/Word/txt/pasted) + Maps (KML/GeoJSON) normalizers
    ai/             Provider abstraction + per-task routing + cost ledger
    agents/         Versioned-prompt runner (prompts live in backend/prompts/)
    services/       classify (cache-forever), narrative+grounding, ingest, finalize
    chat/           Manifest-based orchestrator -> fixed tool vocabulary + undo
    jobs/           Background queue (local thread pool; RQ-ready)
  prompts/          One versioned system prompt per agent — reviewable in git
  scripts/          demo_e2e.py (pipeline proof), seed_demo.py (UI demo data)
  tests/            Rendering primitives + pipeline units
templates/          base/layout.css (shared logic) + 6 token bundles + registry.json
frontend/           Vite + React + TS + Tailwind studio UI
```

## Quickstart

```bash
# Backend
cd backend
pip install -e .[dev]
python -m playwright install chromium   # or set PBG_CHROMIUM_EXECUTABLE
python -m scripts.seed_demo             # optional demo commission
uvicorn app.main:app --port 8000

# Frontend
cd frontend
npm install
npm run dev                             # http://localhost:5173, proxies /api

# Proof-of-pipeline (no AI keys needed)
cd backend && python -m scripts.demo_e2e
```

Provider keys via environment: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`,
`DEEPSEEK_API_KEY`, `OPENAI_API_KEY`; local models via Ollama (BETA, opt-in).

Optional integrations (everything works without them):

- **Google Drive sync** — `PBG_GDRIVE_CLIENT_ID`, `PBG_GDRIVE_CLIENT_SECRET`,
  `PBG_GDRIVE_REFRESH_TOKEN` (OAuth refresh-token flow). Per-project pull of
  photos/notes/map exports and push of rendered PDFs.
- **Places pin enrichment** — `GOOGLE_MAPS_API_KEY`. Maps lists have no public
  API, so KML/GeoJSON export is the ingestion path; Places fills in missing
  categories/coordinates on imported pins.
- **RQ job backend** — `PBG_JOB_BACKEND=rq` + `PBG_REDIS_URL` +
  `pip install .[redis]`. Default is a local thread pool (renders already run
  in fresh subprocesses either way). Falls back to local if Redis is down.

Photo formats: JPEG/PNG/HEIC/TIFF/WebP. Camera RAW is not ingested — export
to JPEG/HEIC first (adding rawpy support would slot into
`photos/pipeline.py::SUPPORTED_EXTS`).

## The rendering architecture (non-negotiable)

Carried from a production 106-page/180-photo build; these are first-class
primitives in `app/rendering/`, not optimizations:

1. **Page-ranged export, never fragment isolation.** A chapter is never rendered
   as a standalone document — pagination drifts. The full monolith is loaded and
   only the needed page range exported (`engine.render_chapter_range`).
2. **Streaming PDF assembly** via qpdf (when installed) or pikepdf — never a
   whole-book in-memory object graph (`assembly.concat_pdfs/extract_page_range`).
3. **String-slicing HTML reassembly.** Chapter fragments are wrapped in
   `<!-- PBG:CHAPTER id -->` markers and spliced by string ops; fragments are
   never DOM-parsed (`assembly.replace_chapter_in_monolith`).
4. **Chunked one-process-per-chunk rendering** engages automatically above a
   measured payload threshold (`PBG_CHUNK_THRESHOLD_MB`, default 200) — fresh
   subprocess per chunk, still rendering from the full document flow.
5. **CSS classes over inline styles** — every visual rule survives build
   pipelines as a class; templates are token bundles over shared layout logic.
6. **Swap/disk preflight** (`/proc/swaps`, free disk) before every heavy render;
   fail fast with an actionable message instead of hanging.

Two render tiers: **Final** (full render, then each chapter's page range cached
as its own PDF) and **Preview** (cached chapters stitched + only dirty chapters
re-exported — cost scales with what changed).

Measured at scale (`scripts/stress_render.py`, this container): a 294MB
payload / 82-page book renders through the chunked path in ~6 min with the
app process peaking at 422MB and each fresh chunk worker under 500MB —
memory stays bounded regardless of book size.

Every page is an explicit fixed-size `.page` element, so the chapter→page map is
computed exactly from the HTML by string scanning — no render needed.

## Grounding (no-fabrication) contract

The Narrative Writer tags every sentence with evidence ids (notes, photo EXIF,
map pins, cited research). A separate, cheaper Grounding Agent audits each
sentence against the evidence content and stores a per-chapter report; the UI
shows "N sentences aren't grounded — review before finalizing." Historical
context is a distinct register and must carry citations (Research Agent).

## Cost discipline

- Every AI call goes through `ai/router.py` and lands in the `ai_runs` ledger
  (provider, model, tokens, estimated cost, task, project, cache-hit).
- Classification is cached forever on content hash; manual overrides are never
  clobbered; near-duplicates (perceptual hash) never spend tokens.
- Per-task provider/model routing is editable in Settings, overridable per
  project; local models are marked BETA.
- The Costs page rolls up spend by project/task/provider/day against each
  book's sale price.
