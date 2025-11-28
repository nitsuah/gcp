# Contributing to GCP Google Drive API Script

Thank you for your interest in contributing to this project! This document provides guidelines for contributing to the Google Drive API folder copy and reporting script.

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
- [ ] Documentation is updated (README, ABOUT, CHANGELOG)
- [ ] Changes are described clearly in PR description
- [ ] No hardcoded credentials or sensitive information

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
