# Contributing to GCP Google Drive API Script

Thank you for your interest in contributing to this project! This document provides guidelines for contributing to the Google Drive API folder copy and reporting script.

## ABOUT

This script utilizes the Google Drive API to enumerate the number of files and folders within a specified folder. It then proceeds to copy the top-level folder contents to a destination folder, with a comprehensive logging mechanism for encountered errors during the copying process. Finally it performs a validation step to ensure that the number of files and folders in the destination folder matches the number of files and folders in the source folder.

### Functions

- `count_files_and_folders(folder_id)`: Counts the number of files and folders in a specified folder.
- `count_child_objects(folder_id)`: Counts the number of child folders in a specified folder recursively.
- `copy_child_objects(source_folder_id, destination_folder_id, max_retries=1)`: Copies all child objects (files and folders) of a specified source folder to a destination folder, with an optional retry mechanism for file copy failures.
- `handle_copy_error(file_or_folder_name, error)`: Handles errors encountered during the copying process.

### Parameters

- `folder_id`: The ID of the folder to count or copy.
- `source_folder_id`: The ID of the source folder to copy.
- `destination_folder_id`: The ID of the destination folder to copy to.
- `file_or_folder_name`: The name of the file or folder that encountered an error.
- `error`: The error encountered during the copying process.

### Implementations

- The script reads the client ID JSON file path from the environment variable `GOOGLE_DRIVE_CLIENT_ID_FILE`.
- It checks if the environment variables for source and destination folders are set and raises a ValueError if they are not.
- The script creates a flow to handle OAuth2 authentication with the Google Drive API.
- It authenticates and authorizes the user using the obtained credentials.
- The script checks if the credentials are valid and prints a message if they are not.
- It creates a Google Drive API service object for interacting with Google Drive.
- The script defines a function to count files and folders, utilizing the Google Drive API to list and count files and folders in a specified folder.
- A function to copy child objects recursively is defined, allowing the script to list files and folders in a specified folder, copy the files to the destination folder, and recursively copy child folders to the destination folder. It includes a retry mechanism for file copy failures.
- A function to handle copy errors is included, which logs errors to a log file and retrieves parent folder URLs if the error is related to copying a file.
- The script defines a function to count child objects recursively, counting child folders in a specified folder and recursively counting child folders in each top-level folder.
- It retrieves the count for the specified folder using the `count_files_and_folders()` function.
- The script writes the results to a CSV file.
- The source folder contents (all files & folders) are copied to the provided destination folder using the `copy_child_objects()` function, including a retry mechanism for file copy failures.

- The script specifically performs three assessments:
  1. **ASSESSMENT 1**: Writes the results of counting all files and folders in a source folder to a CSV file.
  2. **ASSESSMENT 2**: Writes the results of counting all files and folders for the first root children folder, as well as child folders, recursively to a CSV file.
  3. **ASSESSMENT 3**: Copies the source folder contents to the provided destination folder and writes the count of files and child folders found at the destination to a CSV file.

- The script includes a validation step:
  - It compares the CSV reports generated in ASSESSMENT 2 and ASSESSMENT 3 using the `compare_csv_files()` function. The validation is deemed successful if the reports match, and an error message is displayed if they do not.

- The script concludes with a success message indicating that the folder contents have been copied from the source to the destination.

## How to Contribute

1. **Fork the repository** - Create your own fork of the code
2. **Create a feature branch** - `git checkout -b feature/your-feature-name`
3. **Make your changes** - Write clear, concise code with comments
4. **Test your changes** - Ensure the script works with your modifications
5. **Submit a pull request** - Provide a clear description of your changes

## Code Standards

### Python Style Guide

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use meaningful variable and function names
- Add docstrings to all functions using the existing format
- Keep functions focused on a single responsibility
- Use type hints where appropriate

### Code Quality

- **Linting**: Code must pass Pylint checks (see `.github/workflows/pylint.yml`)
- **Security**: Code must pass Bandit security scans
- **Comments**: Add inline comments for complex logic
- **Error Handling**: Use try-except blocks with appropriate error messages

### Example Function Documentation

```python
def function_name(param1, param2):
    """
    Brief description of what the function does.

    Args:
        param1 (type): Description of param1.
        param2 (type): Description of param2.

    Returns:
        return_type: Description of return value.
    """
    # Implementation
```

## Testing

Currently, this project does not have a formal test suite. When adding tests:

- Create a `tests/` directory
- Use `pytest` for test framework
- Name test files with `test_` prefix
- Mock Google Drive API calls to avoid actual API usage
- Test edge cases and error conditions

## Pull Request Process

1. **Update documentation** - Ensure README, ABOUT, and CHANGELOG are updated
2. **Describe changes** - Provide a clear description of what and why
3. **Reference issues** - Link to any related issues
4. **Wait for review** - Maintainers will review and provide feedback
5. **Address feedback** - Make requested changes and update the PR

### PR Checklist

- [ ] Code follows PEP 8 style guidelines
- [ ] Pylint checks pass
- [ ] Bandit security scan passes
- [ ] Unit tests passing (if tests exist)
- [ ] CI YAML added/updated (if applicable)
- [ ] Demo output included (for new features)
- [ ] Documentation is updated (README, CHANGELOG)
- [ ] Changes are described clearly in PR description
- [ ] No hardcoded credentials or sensitive information
- [ ] Can run `pip install -e .` successfully (if packaging added)
- [ ] CLI commands work with `--help` flag (if CLI added)

## Commit Message Format

Use clear, descriptive commit messages:

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring without changing functionality
- **test**: Adding or updating tests
- **chore**: Maintenance tasks, dependency updates

**Example**: `feat: add parallel processing for folder copying`

## Development Setup

### Prerequisites

- Python 3.x
- pip package manager
- Google Cloud Platform account
- OAuth 2.0 Client ID credentials

### Local Setup

```bash
# Clone your fork
git clone https://github.com/your-username/gcp.git
cd gcp

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_DRIVE_CLIENT_ID_FILE='/path/to/client_id.json'
export GOOGLE_DRIVE_SOURCE_FOLDER_ID='source-folder-id'
export GOOGLE_DRIVE_DESTINATION_FOLDER_ID='destination-folder-id'

# Run the script
python copy_folder.py
```

### Environment Variables

- `GOOGLE_DRIVE_CLIENT_ID_FILE`: Path to OAuth2 client credentials JSON
- `GOOGLE_DRIVE_SOURCE_FOLDER_ID`: Google Drive folder ID to copy from
- `GOOGLE_DRIVE_DESTINATION_FOLDER_ID`: Google Drive folder ID to copy to

## Feature Requests

Have an idea for a new feature? Here's how to suggest it:

1. **Check existing issues** - See if it's already been suggested
2. **Open an issue** - Describe the feature and its use case
3. **Discuss** - Engage with maintainers and community
4. **Implement** - If approved, feel free to implement it

## Bug Reports

Found a bug? Help us fix it:

1. **Check existing issues** - See if it's already reported
2. **Create detailed issue** - Include:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Error messages and logs
   - Environment details (Python version, OS, etc.)
3. **Provide context** - Screenshots, CSV files, or log excerpts help

## Questions?

If you have questions about contributing:

- Open an issue with the "question" label
- Review existing documentation (README.md, ABOUT.md)
- Check ROADMAP.md for planned features

## Code of Conduct

Be respectful and inclusive in all interactions. This project follows standard open source community guidelines:

- Be welcoming to newcomers
- Be respectful of differing viewpoints
- Accept constructive criticism gracefully
- Focus on what's best for the community

## License

By contributing to this project, you agree that your contributions will be licensed under the GNU General Public License v3.0.

Thank you for contributing!
