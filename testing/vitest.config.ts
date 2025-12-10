# pytest.ini
# Configuration file for pytest

[pytest]
# Add any additional command line options here
# For example, to specify a specific test file:
# testpaths = tests/test_my_module.py

# Configure test paths
testpaths = tests

# Configure coverage options
# Requires pytest-cov plugin: pip install pytest-cov
addopts = --cov=./ --cov-report term-missing --cov-report html --cov-report xml

# Exclude directories from coverage reporting
# Adjust as needed for your project structure
exclude_dir =
    .venv
    dist
    build
    */migrations/*
    __pycache__

# Minimum coverage percentage
# Fail the build if coverage is below this threshold
# TODO: Set appropriate coverage threshold for the project
# NOTE: Consider setting different thresholds for different parts of the codebase
# cov_fail_under = TODO: VALUE_NEEDED

# Configure markers
# Used to categorize tests (e.g., slow, integration)
# markers =
#     slow: Marks tests as slow
#     integration: Marks integration tests

# Add any custom sections or configurations here