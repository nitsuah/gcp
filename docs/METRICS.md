# Metrics

## Core Metrics

| Metric            | Value | Notes                                                    |
| ----------------- | ----- | -------------------------------------------------------- |
| Code Coverage | 98% (`copy_folder.py`) / 70% total | Docker run 2026-09-24 (PMO audit, `python:3.12-slim`, `pip install -r requirements-dev.txt -e .`): `copy_folder.py` 98% (419 stmts, 7 miss), `retry.py` 96% (27 stmts, 1 miss), `gcp_setup.py` 0% (181 stmts, untested; see TASKS.md). 127 tests pass in ~8s. Command: `pytest tests/ --cov=gcp --cov-report=term-missing`. Needs an editable install: a plain `pip install .` makes tests import the site-packages copy, and coverage reports 0%. |
| Lines of Code | 1491 | `wc -l gcp/*.py` (2026-09-24): `copy_folder.py` 1079, `gcp_setup.py` 334, `retry.py` 75, `__init__.py` 3 |
| Python Files | 4 | `gcp/__init__.py`, `copy_folder.py`, `gcp_setup.py`, `retry.py`. No longer a single implementation file. |
| Test Files | 7 | `test_copy_folder.py`, `test_copy_folder_extended.py`, `test_main.py`, `test_pr59_review_fixes.py`, `test_q3_features.py`, `test_rca_import.py`, `test_roadmap_2026.py` (+ `conftest.py`) |
| Test Cases | 127 | All passing in Docker (2026-09-24) |
| Functions         | ~22   | Core ops + helpers: backoff, MIME filter, skip-existing, permission mirroring, duplicate detection, progress tracking |
| Dependencies      | 5     | pandas, google-api-python-client, auth libraries, pyasn1 |
| CI/CD Workflows   | 6     | Pylint, Bandit, CodeQL, Dependency Review, Docker Smoke, Python CI |
| Assessment Files  | 3     | CSV reports for validation                               |
| Report Files      | 1     | `duplicate-report.csv` (`--duplicate-report`)             |

## Health

| Metric           | Value      | Notes                                         |
| ---------------- | ---------- | --------------------------------------------- |
| Open Issues | 0 | `gh issue list` (2026-09-24) |
| Last Updated | 2026-09-24 | PMO audit: Docker coverage re-run |
| License          | GPL-3.0    | GNU General Public License v3                 |
| Python Version   | 3.10+      | CI matrix: 3.10, 3.11, 3.12                   |
| Security Scans   | 3          | Bandit, CodeQL, Dependency Review             |
