# Tasks

## Done

## In Progress

## Todo

### High Priority - Core Functionality & Documentation

#### A. README.md Enhancement
- [ ] Add TL;DR section at the top
- [ ] Document prerequisites: Python 3.10+, GCP credentials setup
- [ ] Add required scopes for Google Drive API
- [ ] Include `pip install -e .` installation instructions
- [ ] Add example run command:
  ```bash
  GOOGLE_APPLICATION_CREDENTIALS=~/.gcp/creds.json python -m gcp.drive_report --folder-id abc123 --output report.json
  ```
- [ ] Document CSV/JSON output schema with examples
- [ ] Link to `.env.example` file

#### B. Packaging & CLI Entry Points
- [ ] Create/update `pyproject.toml` with PEP 621 format
- [ ] Add console_scripts entry points:
  - `drive-report = gcp.scripts.drive_report:main`
- [ ] Ensure all main modules expose `main()` functions
- [ ] Test `pip install -e .` installation works
- [ ] Verify CLI commands are accessible after install

#### C. Tests & Mocking
- [ ] Create `tests/test_drive_report.py` with pytest
- [ ] Add pytest-mock dependency
- [ ] Mock Google Drive API client with sample dataset
- [ ] Assert JSON output structure correctness
- [ ] Add `pytest.ini` or `tox.ini` configuration
- [ ] Ensure at least one mocked integration test passes

#### D. CI/CD & Security
- [ ] Create `.github/workflows/python-ci.yml`
- [ ] Add workflow steps:
  - Checkout code
  - Setup Python 3.10
  - Install pip-tools
  - Install requirements
  - Run `pytest -q`
  - Run `pylint`
  - Run `bandit -r app/`
- [ ] Verify all CI steps pass

#### E. Examples & Environment Configuration
- [ ] Create `.env.example` with required keys:
  - `GOOGLE_APPLICATION_CREDENTIALS=/path/to/creds.json`
  - `DRIVE_API_SCOPE=https://www.googleapis.com/auth/drive.readonly`
- [ ] Add `examples/report-sample.json` with sample output
- [ ] Document security warning about not committing credentials

### Medium Priority - Enhancements

- [ ] Add progress tracking for large folder operations
- [ ] Implement parallel processing for faster copying
- [ ] Add dry-run mode for testing without actual copying
- [ ] Add support for selective file type filtering
- [ ] Improve error recovery with configurable retry strategies

### Low Priority - Nice to Have

- [ ] Add GUI for starting and monitoring ongoing operations

### Security Notes
- [ ] Audit repository for committed credentials
- [ ] Add warning in README about GOOGLE_APPLICATION_CREDENTIALS
- [ ] Ensure service account keys are in `.gitignore`

## References
- See `AGENT_INSTRUCTIONS.md` for detailed implementation guide
- See `CONTRIBUTING.md` for PR checklist and standards
- See `SECURITY.md` for security requirements
