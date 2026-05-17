# Photo Manager

Offline-first desktop app that watches a local folder for new photos and
ships them to Google Photos on a nightly schedule. State machine + SQLite
guarantee no photo is lost on crash, network drop, or restart.

## Why

- **Reliability over features.** Better to upload 10 photos successfully
  than try to upload 100 and fail.
- **Offline-first.** App keeps queueing while you're offline; syncs the
  moment connectivity returns.
- **State consistency.** Every photo lives in exactly one folder, mirrored
  by one DB row. Crash recovery reconciles the two before anything else
  runs.

## State machine

```
Inbox  --(user flags)-->  Pending  --(scheduler)-->  Uploading
                              ^                          |
                              |                          +-- success ---> Uploaded
                              +-- transient -------------+
                                                         +-- permanent --> Failed
                              <-- manual "Retry Failed" --
```

Subfolders under your library root mirror the states one-to-one:

```
<library_root>/
  Inbox/         newly detected media
  Pending/       flagged for upload
  Uploading/     in flight (never deleted until confirmed)
  Uploaded/2026-05-17/   archived by date
  Failed/        + filename_error.txt sidecar logs
  Temp/          cleaned on each startup
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

On Linux, the OS keychain integration needs a Secret Service backend
(GNOME Keyring or KWallet). Tokens fall back to `~/.local/share/PhotoManager/token.json`
(chmod 600) if no keyring is available.

## First run

1. Launch: `photo-manager`
2. Setup wizard prompts for:
   - **Source folder** (the folder you're watching, e.g. `~/Downloads/Photos`)
   - **Library root** (where the `Inbox/Pending/Uploaded/...` tree lives)
   - **Upload time** (default 02:00)
   - **OAuth client_secret.json** (see below)
3. Click **Connect Google** to run the OAuth flow.

### Creating OAuth credentials

1. Go to https://console.cloud.google.com/
2. New project → enable **Photos Library API**.
3. **APIs & Services → OAuth consent screen** → External, add yourself as a
   test user.
4. **Credentials → Create → OAuth client ID → Desktop app**.
5. Download the JSON file; point Settings → "OAuth client_secret.json" at it.

## Usage

- New files in the source folder appear in `Inbox` automatically (file
  watcher + dedup by SHA1).
- Select photos, click **Flag for upload** → moves to `Pending`.
- The scheduler runs nightly at your configured time. Or click **Upload now**.
- Failures show up in the right panel with their classification. Use
  **Retry failed** to push all of `/Failed` back into `/Pending` with a
  fresh attempt counter.

### CLI

```bash
photo-manager                # GUI
photo-manager --headless     # run the controller without the GUI
photo-manager --upload-now   # one-shot batch and exit (good for cron)
```

## Architecture

| Module | Responsibility |
| --- | --- |
| `models.py` | State enum + legal transitions |
| `database.py` | SQLite, WAL, atomic transitions |
| `folders.py` | Layout + atomic on-disk moves |
| `monitor.py` | Source-folder watcher + dedup ingest |
| `exif.py` | EXIF / hash / format detection |
| `google_photos.py` | API client (uploads/v1 + mediaItems:batchCreate) |
| `auth.py` | OAuth flow + OS keychain storage |
| `retry.py` | Error classification + exponential backoff |
| `network.py` | Connectivity probe + state callbacks |
| `uploader.py` | Engine: pool, timeouts, transitions |
| `recovery.py` | Startup reconciliation + stalled sweep |
| `scheduler.py` | APScheduler cron + manual triggers |
| `app.py` | Wires everything together |
| `ui/` | PyQt6 main window, wizard, settings, tray |

### Invariants enforced in code

- The DB is the source of truth. No process moves a file without first
  (or simultaneously) updating its row.
- A photo's row never says `UPLOADED` unless we hold a `google_photos_id`
  AND the file is in `Uploaded/<date>/`.
- `Uploading` is never the resting state — startup recovery reconciles it
  to `Uploaded` (verified via API) or `Pending` (with bumped retry count).
- Permanent failures (`HTTP_401/403/404`, quota) skip retry; transient
  failures (`HTTP_429/5xx`, timeouts, network) follow the backoff schedule
  in `retry.BACKOFF_SCHEDULE`.

## Tests

```bash
pip install -e '.[dev]'
pytest
```

Covered scenarios (one-to-one with the spec's pre-release checklist):

| Scenario | Test |
| --- | --- |
| Network dropout / retry | `test_uploader.test_transient_503_requeues_and_bumps_attempt` |
| Permanent 403 → `/Failed` | `test_uploader.test_permanent_403_lands_in_failed` |
| Resume on startup | `test_recovery.test_recovery_confirms_upload_visible_in_google` |
| Crash mid-flight, not in Google | `test_recovery.test_recovery_requeues_when_not_in_google` |
| Stalled uploader sweep | `test_recovery.test_sweep_stalled_resets_old_uploading` |
| Max retries exhausted | `test_uploader.test_transient_after_max_retries_moves_to_failed` |
| Dedup | `test_database.test_get_by_hash` |
| Illegal transition rejected | `test_database.test_illegal_transition_rejected` |

## Status

Phase 1 + Phase 2 of the spec are implemented (core MVP + resilience).
Phase 3 UI polish ships at a functional baseline: gallery, metadata
panel, filters, settings, setup wizard, tray icon. Things explicitly
deferred: album assignment UI, weekly summary email, blur detection,
pre-upload compression, advanced quota dashboards. They're hooks rather
than features — the foundations they'd sit on are all here.
