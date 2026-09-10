"""Shared pytest fixtures for the gcp test suite."""

import os
from typing import Callable, ContextManager
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def drive_env() -> Callable[..., ContextManager[None]]:
    """Return a factory for the Google Drive CLI env-var patch context.

    Several CLI-mode tests across test_q3_features.py and test_roadmap_2026.py
    need os.environ patched with the same three GOOGLE_DRIVE_* variables before
    calling main(). Centralizing it here avoids the near-identical patch.dict
    blocks pylint flags as duplicate-code (R0801).
    """

    def _drive_env(
        source: str = "src", dest: str = "dst", client_id_file: str = "fake.json"
    ) -> ContextManager[None]:
        return patch.dict(
            os.environ,
            {
                "GOOGLE_DRIVE_CLIENT_ID_FILE": client_id_file,
                "GOOGLE_DRIVE_SOURCE_FOLDER_ID": source,
                "GOOGLE_DRIVE_DESTINATION_FOLDER_ID": dest,
            },
        )

    return _drive_env


@pytest.fixture
def mock_auth_and_service() -> Callable[..., MagicMock]:
    """Return a factory that wires up the common authenticate+create-service mock pair.

    Many CLI dry-run tests mock authenticate_and_authorize() as valid and stub
    create_drive_service()'s returned service to answer a single files().get()
    call with a folder name. Centralizing that setup avoids near-identical
    blocks pylint flags as duplicate-code (R0801).
    """

    def _setup(
        mock_svc: MagicMock, mock_auth: MagicMock, folder_name: str = "Folder"
    ) -> MagicMock:
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_svc.return_value = svc
        svc.files().get().execute.return_value = {"name": folder_name}
        return svc

    return _setup
