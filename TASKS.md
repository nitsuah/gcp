# Tasks

Last Updated: 2026-04-03 (pmo/q2-2026-planning)

## Done

- [x] Ship the assessment scripts and validate output artifacts.
- [x] Add automated tests for copy logic and CLI entry paths.
- [x] Add CI security workflows.
- [x] Publish setup and environment docs in README and `.env.example`.
- [x] Fix the Docker build failure in `Dockerfile`.
  - Completed: 2026-03-27
  - Evidence: `docker build -t gcp-devops-check .` succeeds from repo root and the image runs `drive-copy --help`.
- [x] Add a Docker smoke test to CI.
  - Completed: 2026-03-27
  - Evidence: `.github/workflows/docker-smoke.yml` builds the image and runs `drive-copy --help`.
- [x] Align README examples with the shipped CLI.
  - Completed: 2026-03-27
  - Evidence: README usage now lists `drive-copy` as canonical with valid `--help-env` and module-based alternatives.
- [x] Add a `--dry-run` option for copy workflows.
  - Completed: 2026-03-27
  - Evidence: `drive-copy --dry-run` now previews scope without creating output files or issuing copy calls.

## In Progress

## Todo

## Done

- [x] Add progress telemetry for long-running copy operations.
  - Completed: 2026-04-03
  - Evidence: `gcp/copy_folder.py` now logs periodic `COPY PROGRESS` updates plus a final `COPY PROGRESS SUMMARY` with elapsed duration; covered by `tests/test_copy_folder_extended.py`.

