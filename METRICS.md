# Metrics

## Core Metrics

| Metric            | Value | Notes                                                    |
| ----------------- | ----- | -------------------------------------------------------- |
| Code Coverage     | ~10%  | estimated (manual analysis). Only auth & counting (3/9 funcs) tested. Main logic untested. |
| Lines of Code     | ~450  | Single Python file (copy_folder.py)                      |
| Python Files      | 1     | Main script file                                         |
| Test Files        | 1     | tests/test_copy_folder.py                                |
| Test Cases        | 7     | Auth success/fail, Create Service, File Counting (Empty/Items) |
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
| Last Updated     | 2025-11-27 | Documentation compliance update               |
| License          | GPL-3.0    | GNU General Public License v3                 |
| Python Version   | 3.x        | Compatible with Python 3.x                    |
| Security Scans   | 3          | Bandit, CodeQL, Dependency Review             |
