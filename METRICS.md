# Metrics

## Core Metrics

| Metric            | Value | Notes                                                    |
| ----------------- | ----- | -------------------------------------------------------- |
| Code Coverage     | 98%   | ✅ Comprehensive test coverage (Target: 75%+). All functions tested including main() CLI. Only 3 lines unreachable dead code. |
| Lines of Code     | ~450  | Single Python file (copy_folder.py)                      |
| Python Files      | 1     | Main script file                                         |
| Test Files        | 3     | test_copy_folder.py, test_copy_folder_extended.py, test_main.py |
| Test Cases        | 33    | Auth, file ops, recursive counting, copying with retry, error handling, CSV operations, main() workflow |
| Functions         | 9     | copy_child, count_child, auth, service, handle_error, etc |
| Dependencies      | 4     | pandas, google-api-python-client, auth libraries         |
| CI/CD Workflows   | 4     | Pylint, Bandit, CodeQL, Dependency Review                |
| Assessment Files  | 3     | CSV reports for validation                               |
| Execution Time    | TBD   | Depends on folder size and Google Drive API rate limits  |

## Health

| Metric           | Value      | Notes                                         |
| ---------------- | ---------- | --------------------------------------------- |
| Open Issues      | 0          | No open issues                                |
| Health Score     | TBD        | Awaiting Overseer evaluation                  |
| Last Updated     | 2025-01-12 | Test coverage expansion to 98%                |
| License          | GPL-3.0    | GNU General Public License v3                 |
| Python Version   | 3.x        | Compatible with Python 3.x                    |
| Security Scans   | 3          | Bandit, CodeQL, Dependency Review             |
