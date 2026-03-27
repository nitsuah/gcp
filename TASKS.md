# Tasks

## Done

- [x] Shipped assessment scripts and validated output artifacts (`outputs/assessment-1.csv`, `outputs/assessment-2.csv`, `outputs/assessment-3.csv`).
- [x] Added core automated tests for copy logic and CLI entry paths.
- [x] Added CI security workflows (pylint, bandit, codeql, dependency review).
- [x] Published setup and environment docs in README and `.env.example`.

## In Progress

- [ ] P0 | Bug | Confidence: High | Fix Docker build failure in `Dockerfile`.
  - Problem: `docker build` fails because `COPY copy_folder.py .` references a file that does not exist at repo root.
  - Impact: Containerized usage path is broken and cannot be deployed reliably.
  - Acceptance Criteria: Docker image builds successfully from repo root and `drive-copy` runs without file-not-found errors.
  - Dependencies: None.

## Todo

- [ ] P1 | Reliability | Confidence: High | Add Docker smoke test to CI.
  - Problem: Current CI validates lint/security but not container runtime behavior.
  - Impact: Build/runtime container regressions can ship undetected.
  - Acceptance Criteria: A workflow builds the Docker image and runs a basic command successfully.
  - Dependencies: Dockerfile fix.

- [ ] P1 | Docs | Confidence: High | Align README command examples with actual packaged CLI.
  - Problem: Some historical command examples and module paths are inconsistent with current structure.
  - Impact: Slower onboarding and support overhead.
  - Acceptance Criteria: README shows one canonical run path and one alternate path that both execute successfully.
  - Dependencies: None.

- [ ] P2 | Feature | Confidence: Medium | Add `--dry-run` option for copy workflow.
  - Problem: Users cannot validate intended copy operations safely before writing changes.
  - Impact: Increased operational risk on production folders.
  - Acceptance Criteria: CLI supports dry-run mode with summary output and no writes.
  - Dependencies: Stable command argument parser.

- [ ] P2 | Feature | Confidence: Medium | Add progress telemetry for long-running copy operations.
  - Problem: Large copy jobs provide limited visibility.
  - Impact: Operators cannot estimate completion or detect stalls quickly.
  - Acceptance Criteria: Log periodic progress updates and final duration summary.
  - Dependencies: None.

