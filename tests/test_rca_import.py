"""
RCA (Root Cause Analysis) regression test.

Root cause: logging.basicConfig(filename=LOG_FILE_PATH) was called at module
level in gcp/copy_folder.py.  Python's FileHandler opens the target file
immediately, so if the 'outputs/' directory did not exist in the process's
current working directory the import raised FileNotFoundError and every test
that imported from gcp.copy_folder failed.

These tests confirm that the module can be imported successfully regardless of
whether 'outputs/' is present in the current directory, and that main() still
creates the log file under outputs/ when it actually runs.
"""
# pylint: disable=redefined-outer-name,import-outside-toplevel
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
import gcp.copy_folder as cf


# Project root (two levels up from this test file) used as PYTHONPATH in
# subprocess tests so that 'import gcp.copy_folder' resolves correctly.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def subprocess_env():
    """Return an environment dict with PYTHONPATH pointing at the project root."""
    return {**os.environ, "PYTHONPATH": _PROJECT_ROOT}


class TestImportWithoutOutputsDirectory:
    """Verify the module imports cleanly even when outputs/ does not exist."""

    def test_import_succeeds_from_fresh_directory(self, tmp_path, subprocess_env):
        """
        RCA regression: importing gcp.copy_folder must not raise
        FileNotFoundError when the outputs/ directory is absent.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import gcp.copy_folder; print('import ok')",
            ],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env=subprocess_env,
            check=False,
        )
        assert result.returncode == 0, (
            f"Import failed in directory without outputs/.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "import ok" in result.stdout

    def test_import_does_not_create_outputs_directory(self, tmp_path, subprocess_env):
        """
        A side-effect-free import must not create the outputs/ directory.
        The outputs directory should only be created when main() is called.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import gcp.copy_folder",
            ],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env=subprocess_env,
            check=False,
        )
        assert result.returncode == 0
        assert not (tmp_path / "outputs").exists(), (
            "Importing the module must not create the outputs/ directory."
        )


class TestMainCreatesOutputsDirectory:
    """Verify main() creates the outputs directory and log file when it runs."""

    def test_main_creates_outputs_dir(self, tmp_path, monkeypatch):
        """main() must create outputs/ if it does not already exist."""
        monkeypatch.setattr(cf, "OUTPUTS_DIRECTORY", str(tmp_path / "outputs") + "/")

        env_vars = {
            "GOOGLE_DRIVE_CLIENT_ID_FILE": "client.json",
            "GOOGLE_DRIVE_SOURCE_FOLDER_ID": "src123",
            "GOOGLE_DRIVE_DESTINATION_FOLDER_ID": "dst456",
        }
        mock_service = MagicMock()
        mock_service.files().get().execute.side_effect = [
            {"name": "Source"},
            {"name": "Dest"},
        ]

        with patch("os.environ.get", side_effect=env_vars.get), \
             patch("gcp.copy_folder.authenticate_and_authorize",
                   return_value=MagicMock()), \
             patch("gcp.copy_folder.create_drive_service",
                   return_value=mock_service), \
             patch("gcp.copy_folder.count_child_objects", return_value=(5, 2)), \
             patch("gcp.copy_folder.add_child_folders"), \
             patch("gcp.copy_folder.copy_child_objects"), \
             patch("gcp.copy_folder.compare_csv_files"), \
             patch("builtins.open"):
            cf.main()

        assert (tmp_path / "outputs").is_dir(), (
            "main() must create the outputs/ directory if it does not exist."
        )
