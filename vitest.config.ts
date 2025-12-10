# pytest.ini
# Configuration file for pytest.

[pytest]
# Add any additional command line options here
# e.g., --strict-markers, --tb=short, etc.
addopts = -v --cov=./ --cov-report term-missing

# Define test file naming convention
python_files = test_*.py *_test.py

# Define directories to ignore during test collection
# e.g., virtual environments, build directories, etc.
norecursedirs = .git __pycache__ venv dist build

# Coverage configuration
[coverage:run]
# Source files to measure coverage for
source = .

# Exclude patterns from coverage analysis
exclude =
    */__init__.py
    .venv/*
    */test_*.py
    *_test.py
    */setup.py
    */conftest.py  # Exclude pytest configuration files

[coverage:report]
# Fail if coverage is below this percentage
fail_under = 80 # TODO: VALUE_NEEDED - Set appropriate coverage threshold

# Exclude files based on regex patterns
exclude_lines =
    pragma: no cover
    raise NotImplementedError
    raise AssertionError
    if __name__ == .__main__.:

# Coverage HTML report directory
html_dir = coverage_html_report # TODO: VALUE_NEEDED - Set report directory if needed