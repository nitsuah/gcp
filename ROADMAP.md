# GCP Google Drive Tools Roadmap

## 2026 Q1 (Completed)

- [x] Delivered three assessment workflows (root counts, recursive counts, and copy validation)
- [x] Added pytest suite for copy and CLI paths
- [x] Added security and quality workflows (pylint, bandit, codeql, dependency review)
- [x] Documented environment-based OAuth setup and CLI usage

## 2026 Q2 (In Progress)

- [ ] Fix Docker image build path and runtime command so container execution matches repository layout
- [ ] Add Docker smoke validation to CI to prevent container regressions
- [ ] Normalize README examples to match the shipped `drive-copy` entrypoint

## 2026 Q3 (Planned)

- [ ] Add dry-run mode for copy operations
- [ ] Add progress telemetry for large folder copies
- [ ] Add selective copy filters by file type

## 2026 Q4 (Exploratory)

- [ ] Evaluate lightweight web UI for credential and folder configuration
- [ ] Evaluate safe parallel copy strategy with bounded retries and rate-limit awareness

