# Metrics

## Core Metrics

| Metric            | Value | Notes                                                    |
| ----------------- | ----- | -------------------------------------------------------- |
| Code Coverage     | 98% (`copy_folder.py`) / 62% total | Docker run 2026-08-23: `copy_folder.py` 98% (309 stmts, 7 miss); `gcp_setup.py` 0% (not yet tested, 181 stmts); 80 tests pass in 7.18s. Command: `pytest tests/ --cov=gcp --cov-report=term` |
| Lines of Code     | ~750  | `gcp/copy_folder.py`                                     |
| Python Files      | 1     | Single implementation file                               |
| Test Files        | 5     | `test_copy_folder.py`, `test_copy_folder_extended.py`, `test_main.py`, `test_q3_features.py`, `test_rca_import.py` |
| Test Cases        | 80    | Auth, file ops, recursive counting, copying with retry, MIME filters, exponential backoff, parallel copy, skip-existing, CLI args |
| Functions         | ~18   | Core ops + helpers: backoff, MIME filter, skip-existing, progress tracking |
| Dependencies      | 5     | pandas, google-api-python-client, auth libraries, pyasn1 |
| CI/CD Workflows   | 6     | Pylint, Bandit, CodeQL, Dependency Review, Docker Smoke, Python CI |
| Assessment Files  | 3     | CSV reports for validation                               |

## Health

| Metric           | Value      | Notes                                         |
| ---------------- | ---------- | --------------------------------------------- |
| Open Issues      | 0          | No open issues                                |
| Last Updated     | 2026-08-23 | Docker coverage run (pytest --cov=gcp)        |
| License          | GPL-3.0    | GNU General Public License v3                 |
| Python Version   | 3.10+      | CI matrix: 3.10, 3.11, 3.12                   |
| Security Scans   | 3          | Bandit, CodeQL, Dependency Review             |
