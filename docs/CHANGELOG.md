# Changelog

> 🧭 [gcp](../README.md) · [Features](./FEATURES.md) · [Roadmap](./ROADMAP.md) · [Tasks](./TASKS.md) · **Changelog** · [Metrics](./METRICS.md) <!-- nav -->

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- CI: pull requests now run the shared risk guard check (`.github/workflows/risk-guard.yml`) (#118).
- Extracted the allowed-host check from server.js into apps/lib/host-allowlist.js with unit tests; no behaviour change.
- Extracted the login failure limiter from server.js into apps/lib/login-limiter.js with unit tests; no behaviour change.
- Extracted cookie parsing and constant-time comparison from server.js into apps/lib/http-utils.js with unit tests; no behaviour change.
- Dependencies: `requirements.txt` sets floors on the transitive `certifi` (>=2026.10.18), `protobuf` (>=5.29.6) and `idna` (>=3.15) so no resolver picks a release with PYSEC-2026-4320, PYSEC-2026-1805 or PYSEC-2026-215; the repo-health workflow uses the shared kit at `a0df883`, whose own lockfile no longer carries the stale `msgpack` advisory.
- Dependencies: `pandas` 3.1.1 on Python 3.11+ (Python 3.10 stays on 2.3.3 through an environment marker, since pandas 3 needs 3.11) and `google-api-python-client` 2.202.0. In `apps/`, `express` 4 → 5.3, `dotenv` 16 → 18 (loaded with `quiet: true` to keep startup output unchanged) and `googleapis` 189 → 190. `pip-audit` and `npm audit` report no known vulnerabilities.
- Retry backoff jitter and generated project-ID suffixes use `secrets.SystemRandom` (same API, same ranges); `tests/test_retry.py` covers the jitter range and the backoff cap.

### Fixed

- `POST /api/gemini/query` no longer throws `TypeError` when `prompt` is missing or non-string: demo branch uses empty string fallback, real branch keeps default greeting; numeric `prompt` values are handled gracefully.

### Security

- The Google sign-in flow now sends a random `state` (bound to the browser with an HttpOnly cookie, single use, 10 minute lifetime) and a PKCE `S256` challenge; `/oauth2callback` rejects requests whose state is missing, reused or does not match, and passes the code verifier on the token exchange.
- `apps/server.js` now binds to `127.0.0.1` by default (`HOST` to change it) and requires an access token (`APP_AUTH_TOKEN`, or a one-time token printed at startup) for `/api/*`, `/connect-google` and `/oauth2callback`; the dashboard asks for it and keeps it in an HttpOnly session cookie. A non-loopback `HOST` without `APP_AUTH_TOKEN` is refused at startup, `APP_AUTH_DISABLED=1` is a loopback-only local-dev opt-out, and requests with an unexpected `Host` header are rejected. The container image sets `HOST=0.0.0.0`, so pass `APP_AUTH_TOKEN` and publish the port to loopback (`-p 127.0.0.1:3000:3000`).
- The dashboard (`apps/public/app.js`) HTML-escapes account emails, message headers and snippets, Gemini output and console messages before rendering them (shared `escapeHtml` helper in `apps/public/escape.js`).
- `apps/Dockerfile` no longer copies `.env` into the image (configuration is passed at runtime, e.g. `docker run --env-file .env`), and `apps/.dockerignore` excludes `.env*` and `client_secret*.json` (including in subdirectories) from the build context; `ENCRYPTION_KEY` is documented as a runtime variable. `apps/test/docker.test.js` checks both.
- The token store in `apps/server.js` now uses AES-256-GCM (authenticated) with a per-write random salt and a scrypt-derived key; the 16-byte tag length is enforced. Existing `tokens.json` files written in the previous AES-256-CBC format are read and re-written in the new format automatically on first load, so no re-authorization is needed. After that, the old format is refused (marker file `tokens.json.v2`), and writes are atomic (temp file + rename) and report failures. The token directory can be moved with `DATA_DIR` (default unchanged: `apps/data`), which the tests use for isolated stores.
- The demo sign-in code and `demo-` account shortcuts in `apps/server.js` only apply while demo mode is active (no OAuth credentials); with real credentials they are ignored. Demo tokens always go to `data/tokens.demo.json`, even when `ENCRYPTION_KEY` is set (the store is chosen per call from the credentials currently found). `DATA_DIR` can relocate the data directory.
- `apps/server.js` no longer falls back to a hard-coded token-encryption key: `ENCRYPTION_KEY` is required and the server exits at startup if it is missing (demo mode, with no OAuth credentials, uses a clearly marked dev-only key). Tokens encrypted with the old default key cannot be read with a new key, so linked accounts must be re-authorized. Demo mode now stores its mock tokens in `data/tokens.demo.json`, leaving `data/tokens.json` untouched.

### Changed

- gcp_setup runs gcloud with argument lists instead of shell strings.

### 2026-09 — Hardening & coverage

- `gcp/gcp_setup.py` covered by `tests/test_gcp_setup.py` (51 tests, `subprocess` mocked): the module went from 0% to 99%, and total coverage from 70% to 99% (#67, #68).
- `gcp_setup` now shows the gcloud login prompt and validates typed project/billing IDs (#69).
- Python dependencies pinned with a `pip-audit` CI signal (#63); Bandit scan excludes `tests/`/`testing/` (#66); `apps/` `qs` bumped to 6.16.0 for Dependabot alerts #9/#10 (#64); CodeQL action v4 and grouped Actions/Python bumps (#60–#62).
- Planning docs reset for 2027 (`pmo-ff`): completed 2026 roadmap sections removed, the web-UI evaluation carried into 2027 Q1, breadcrumb navigation + README docs index added.

### Added (Q4 2026)

- **Tests for accounts-config endpoints** (`apps/test/accounts-config.test.js`): covers `POST /api/config/drive-logging` (enable/disable, missing body), `POST /api/accounts/disconnect` (404 for unknown, remove linked demo account, idempotent second disconnect), and auth requirement on both routes.
- **Duplicate-detection report** (`--duplicate-report`): recursively scans the source and
  destination folder trees and writes `outputs/duplicate-report.csv` listing files with
  identical name and byte size found in both — useful for spotting redundant copies before
  or after a migration. Runs as a standalone report mode (exits without copying); Google-native
  files (Docs, Sheets, Slides, ...) are excluded since they have no byte size to compare.
- **Permission mirroring** (`--mirror-permissions`): copies sharing/ACL permissions from each
  source file and folder onto its newly created destination counterpart as it is copied, so
  migrated content keeps its original collaborators instead of defaulting to
  destination-owner-only access. Ownership is never mirrored (Drive requires a separate
  ownership-transfer flow); a permission that fails to apply (e.g. a domain grant that doesn't
  exist in the destination org) is logged and skipped without aborting the copy. Applies only
  to objects copied/created during the run, not ones reused via `--skip-existing`.
- **`tests/test_roadmap_2026.py`**: new tests covering duplicate detection (recursive listing,
  name+size matching, CSV output) and permission mirroring (role/type handling, error handling,
  end-to-end wiring through `copy_child_objects` and the CLI).

### Deferred

- **Lightweight web UI for credential/folder configuration** — evaluated and deferred to 2027;
  see the "2027" section of ROADMAP.md for scope and reasoning.

### Added (Q3 2026)

- **Selective copy filters by file type** (`--include-mime`, `--exclude-mime`): copy only docs,
  PDFs, images, or any MIME type pattern; aliases like `docs`, `sheets`, `pdf`, `images` expand
  to full MIME strings; prefix patterns (e.g. `image/`) match all subtypes.
- **Exponential backoff with rate-limit awareness**: retry loop now backs off exponentially
  (starting at 1 s, capped at `--max-backoff`, default 60 s) with jitter; 429/503 responses
  are logged at WARNING rather than ERROR to distinguish rate-limiting from hard failures.
- **Parallel file copy** (`--workers N`): ThreadPoolExecutor-based parallel copy of files
  within each folder level; folder creation remains sequential to preserve parent IDs.
- **`--max-retries` CLI arg**: configures per-file retry attempts (previously hardcoded to 1).
- **`--max-backoff` CLI arg**: caps the exponential backoff delay in seconds.
- **`skipped_files` counter** added to progress telemetry and final summary when MIME filters
  are active.
- **Incremental / skip-existing copy** (`--skip-existing`): files already present in the
  destination are skipped rather than duplicated; existing subfolders are reused rather than
  recreated — enables safe re-runs after partial failures.
- **`tests/test_q3_features.py`**: 35 new tests covering MIME filter helpers,
  filtered counts, filtered copy, exponential backoff, parallel copy, skip-existing, and CLI args.

### Added

- Tests for the dashboard sign-in retry wrapper.
- Documentation compliance updates for Overseer standards
- FEATURES.md with comprehensive feature documentation
- CHANGELOG.md to track version history
- CONTRIBUTING.md with contribution guidelines

### Changed

- Agent instructions (`.github/copilot-instructions.md`) now require closing tracked work in the same PR: update `docs/TASKS.md`, `docs/ROADMAP.md` and this changelog before the last push, and confirm `git diff origin/<base>...HEAD --stat` against the PR's base branch includes them before merge; added `.github/pull_request_template.md` with a "Closes TASKS item(s)" checklist.
- Updated ROADMAP.md to quarterly format with completion status
- Updated TASKS.md with proper section structure (Done, In Progress, Todo)
- Updated METRICS.md with accurate project metrics

## [1.0.0] - 2023-11-01

### Added

- Initial release of Google Drive API script
- OAuth2 authentication and authorization flow
- Assessment 1: Root folder file and folder counting
- Assessment 2: Recursive child object counting with detailed CSV reports
- Assessment 3: Folder copying with validation
- Recursive folder copying with structure preservation
- Retry mechanism for file copy failures
- Comprehensive error handling and logging system
- CSV-based validation comparing source and destination
- Environment variable configuration for folder IDs and client credentials
- CI/CD workflows: Pylint, Bandit, CodeQL, Dependency Review
- README.md with setup instructions and badges
- ABOUT.md with detailed implementation documentation
- Support for trashed file filtering

### Fixed

- Error handling for failed file copy operations with parent folder URL retrieval
