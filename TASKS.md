# Tasks

Last Updated: 2026-03-27

## Done

- [x] Ship the assessment scripts and validate output artifacts.
- [x] Add automated tests for copy logic and CLI entry paths.
- [x] Add CI security workflows.
- [x] Publish setup and environment docs in README and `.env.example`.

## In Progress

- [ ] Fix the Docker build failure in `Dockerfile`.
  - Priority: P0
  - Problem: `docker build` still references `copy_folder.py` at the wrong path.
  - Acceptance Criteria: the image builds from repo root and runs the packaged entrypoint cleanly.

## Todo

- [ ] Add a Docker smoke test to CI.
  - Priority: P1
  - Problem: CI still misses container runtime regressions.
  - Acceptance Criteria: the workflow builds the image and runs a basic command successfully.

- [ ] Align README examples with the shipped CLI.
  - Priority: P1
  - Problem: command examples and module paths have drifted from the packaged entrypoint.
  - Acceptance Criteria: README shows one canonical path and one valid alternate path.

- [ ] Add a `--dry-run` option for copy workflows.
  - Priority: P2
  - Problem: users cannot preview planned copy operations safely.
  - Acceptance Criteria: the CLI supports dry-run mode with summary output and no writes.

- [ ] Add progress telemetry for long-running copy operations.
  - Priority: P2
  - Problem: large copy jobs still provide poor visibility.
  - Acceptance Criteria: the tool logs periodic progress updates and a final duration summary.

