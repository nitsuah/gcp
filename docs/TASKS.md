# Tasks

Last Updated: 2026-09-24

All completed work is documented in [FEATURES.md](FEATURES.md) and [CHANGELOG.md](CHANGELOG.md).

## In Progress

## Todo

- [x] Add tests for `gcp/gcp_setup.py` (0% coverage, 181 statements). Done 2026-09-24: `tests/test_gcp_setup.py` (51 tests) brings `gcp_setup.py` to 99% and total to 99%.
  - Priority: P2 · Type: Tech Debt · Confidence: High
  - Problem: the 2026-09-24 PMO Docker coverage run shows `gcp_setup.py` at 0%. It is the only untested module and accounts for 181 of the 189 missed statements. Without it, total coverage would be ~98%; with it, total is 70%. METRICS.md has called it "not yet tested" since 2026-09-02, but TASKS had no item for it.
  - Acceptance Criteria: unit tests cover `gcp_setup.py`'s gcloud wrapper functions (`run_command` and its arg redaction, billing-account selection, project creation, `enable_apis`, `create_budget`, OAuth client creation, `write_client_secrets`) with `subprocess` mocked, so no real gcloud calls are made, and total coverage in `docs/METRICS.md` is re-measured.

- [ ] Evaluate lightweight web UI for credential and folder configuration (deferred to 2027, see ROADMAP.md)
