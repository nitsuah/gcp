# GCP Google Drive Tools Roadmap

Last Updated: 2026-06-02 (dev-q3)

## 2026 Q1 (Completed)

- [x] Deliver the three assessment workflows.
- [x] Add pytest coverage for copy and CLI paths.
- [x] Add security and quality workflows.
- [x] Document OAuth setup and CLI usage.

## 2026 Q2 (Completed)

- [x] Fix the Docker image build and runtime path.
- [x] Add Docker smoke validation to CI.
- [x] Normalize README examples around the `drive-copy` entrypoint.
- [x] Add `--dry-run` mode for copy operations.

## 2026 Q3 (In Progress → dev-q3)

- [x] Add progress telemetry for large folder copies.
- [x] Add selective copy filters by file type (`--include-mime` / `--exclude-mime` with aliases).
- [x] Exponential backoff with rate-limit (429/503) awareness and jitter.
- [x] Parallel file copy with bounded concurrency (`--workers N`).
- [x] Configurable `--max-retries` and `--max-backoff` CLI args.

## 2026 Q4 (Exploratory)

- [ ] Evaluate a lightweight web UI for credential and folder configuration.
- [ ] Evaluate resumable / incremental copy (skip already-copied files in destination).

