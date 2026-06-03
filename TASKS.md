# Tasks

Last Updated: 2026-06-02 (dev-q3)

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

- [x] Add selective copy filters by file type (`--include-mime` / `--exclude-mime`).
  - Completed: 2026-06-02 (dev-q3)
  - Evidence: `--include-mime docs,pdf` restricts copy to matching MIME types; `--exclude-mime images`
    skips image files; short aliases expand to full MIME strings; prefix patterns (e.g. `image/`)
    match all subtypes; filtered counts propagate through `count_child_objects` for accurate dry-run output;
    skipped files logged in progress telemetry; covered by `tests/test_q3_features.py`.

- [x] Exponential backoff with rate-limit awareness.
  - Completed: 2026-06-02 (dev-q3)
  - Evidence: `_copy_file_with_backoff` retries with exponential delay (base 1 s, jitter, cap via `--max-backoff`);
    HTTP 429/503 logged at WARNING; `--max-retries` and `--max-backoff` are configurable CLI args;
    covered by `tests/test_q3_features.py::TestCopyFileWithBackoff`.

- [x] Parallel file copy with bounded concurrency (`--workers N`).
  - Completed: 2026-06-02 (dev-q3)
  - Evidence: `--workers 4` copies files within each folder using `ThreadPoolExecutor`; folder creation
    stays sequential to preserve parent IDs; works in combination with MIME filters; covered by
    `tests/test_q3_features.py::TestParallelCopy`.

