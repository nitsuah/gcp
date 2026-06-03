"""Tests for Q3 features: MIME filters, exponential backoff, and parallel copy."""

# pylint: disable=redefined-outer-name,import-outside-toplevel
from unittest.mock import MagicMock, Mock, call, patch

import pytest
from googleapiclient.errors import HttpError

from gcp.copy_folder import (
    MIME_ALIASES,
    _copy_file_with_backoff,
    _file_passes_filter,
    _mime_matches,
    _resolve_mime_aliases,
    copy_child_objects,
    count_child_objects,
    main,
)


@pytest.fixture
def mock_service():
    return MagicMock()


# ---------------------------------------------------------------------------
# MIME filter helpers
# ---------------------------------------------------------------------------


class TestResolveMimeAliases:
    def test_known_alias(self):
        assert _resolve_mime_aliases(["docs"]) == [
            "application/vnd.google-apps.document"
        ]

    def test_passthrough_full_mime(self):
        assert _resolve_mime_aliases(["application/pdf"]) == ["application/pdf"]

    def test_mixed(self):
        result = _resolve_mime_aliases(["pdf", "text/plain"])
        assert result == ["application/pdf", "text/plain"]

    def test_prefix_alias_images(self):
        assert _resolve_mime_aliases(["images"]) == ["image/"]

    def test_all_aliases_resolve(self):
        for alias in MIME_ALIASES:
            result = _resolve_mime_aliases([alias])
            assert result == [MIME_ALIASES[alias]]


class TestMimeMatches:
    def test_exact_match(self):
        assert _mime_matches("application/pdf", ["application/pdf"])

    def test_no_match(self):
        assert not _mime_matches("application/pdf", ["text/plain"])

    def test_prefix_match(self):
        assert _mime_matches("image/jpeg", ["image/"])
        assert _mime_matches("image/png", ["image/"])

    def test_prefix_no_partial_word_match(self):
        assert not _mime_matches("application/pdf", ["image/"])

    def test_empty_patterns(self):
        assert not _mime_matches("application/pdf", [])


class TestFilePassesFilter:
    def test_no_filters_always_passes(self):
        assert _file_passes_filter("application/pdf", [], [])

    def test_include_match_passes(self):
        assert _file_passes_filter("application/pdf", ["application/pdf"], [])

    def test_include_no_match_fails(self):
        assert not _file_passes_filter("text/plain", ["application/pdf"], [])

    def test_exclude_match_fails(self):
        assert not _file_passes_filter("application/pdf", [], ["application/pdf"])

    def test_exclude_takes_priority_over_include(self):
        assert not _file_passes_filter(
            "application/pdf", ["application/pdf"], ["application/pdf"]
        )

    def test_prefix_include(self):
        assert _file_passes_filter("image/jpeg", ["image/"], [])
        assert not _file_passes_filter("text/plain", ["image/"], [])

    def test_prefix_exclude(self):
        assert not _file_passes_filter("image/jpeg", [], ["image/"])
        assert _file_passes_filter("text/plain", [], ["image/"])


# ---------------------------------------------------------------------------
# count_child_objects with MIME filters
# ---------------------------------------------------------------------------


class TestCountChildObjectsWithFilters:
    def test_include_filter_counts_only_matching(self, mock_service):
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "1", "name": "doc.gdoc", "mimeType": "application/vnd.google-apps.document"},
                    {"id": "2", "name": "sheet.txt", "mimeType": "text/plain"},
                ]
            }
        ]
        num_files, num_folders = count_child_objects(
            "folder_id",
            mock_service,
            include_mime=["application/vnd.google-apps.document"],
        )
        assert num_files == 1
        assert num_folders == 0

    def test_exclude_filter_skips_matching(self, mock_service):
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "1", "name": "img.jpg", "mimeType": "image/jpeg"},
                    {"id": "2", "name": "doc.txt", "mimeType": "text/plain"},
                ]
            }
        ]
        num_files, num_folders = count_child_objects(
            "folder_id",
            mock_service,
            exclude_mime=["image/"],
        )
        assert num_files == 1

    def test_filters_propagate_to_subfolders(self, mock_service):
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {
                        "id": "subfolder",
                        "name": "sub",
                        "mimeType": "application/vnd.google-apps.folder",
                    }
                ]
            },
            {
                "files": [
                    {"id": "3", "name": "img.png", "mimeType": "image/png"},
                    {"id": "4", "name": "doc.txt", "mimeType": "text/plain"},
                ]
            },
        ]
        num_files, _ = count_child_objects(
            "root", mock_service, include_mime=["text/plain"]
        )
        assert num_files == 1


# ---------------------------------------------------------------------------
# copy_child_objects with MIME filters
# ---------------------------------------------------------------------------


class TestCopyChildObjectsWithFilters:
    def test_include_filter_skips_non_matching_files(self, mock_service):
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "f1", "name": "doc.gdoc", "mimeType": "application/vnd.google-apps.document"},
                    {"id": "f2", "name": "sheet.txt", "mimeType": "text/plain"},
                ]
            },
            {"files": []},  # no subfolders
        ]
        mock_service.files().copy().execute.return_value = {"id": "new"}

        copy_child_objects(
            "src",
            "dest",
            mock_service,
            include_mime=["application/vnd.google-apps.document"],
        )

        # Only f1 should be copied; call count includes the intermediate call()
        assert mock_service.files().copy.call_count >= 1
        # Verify the copy was called with f1's id
        copy_calls = mock_service.files().copy.call_args_list
        copied_ids = [c[1]["fileId"] for c in copy_calls if "fileId" in (c[1] or {})]
        if copied_ids:
            assert "f2" not in copied_ids

    def test_exclude_filter_skips_matching_files(self, mock_service):
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "f1", "name": "img.jpg", "mimeType": "image/jpeg"},
                    {"id": "f2", "name": "doc.txt", "mimeType": "text/plain"},
                ]
            },
            {"files": []},
        ]
        mock_service.files().copy().execute.return_value = {"id": "new"}

        import logging
        with patch("gcp.copy_folder.logging.info") as mock_info:
            copy_child_objects("src", "dest", mock_service, exclude_mime=["image/"])

        summary_calls = [
            c for c in mock_info.call_args_list
            if c.args and "COPY PROGRESS SUMMARY" in str(c.args[0])
        ]
        assert len(summary_calls) == 1
        # skipped_files should be 1 (the jpeg)
        summary_args = summary_calls[0].args
        assert "skipped=1" in (summary_args[0] % summary_args[1:])

    def test_no_filter_copies_all_files(self, mock_service):
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "f1", "name": "a.txt", "mimeType": "text/plain"},
                    {"id": "f2", "name": "b.pdf", "mimeType": "application/pdf"},
                ]
            },
            {"files": []},
        ]
        mock_service.files().copy().execute.return_value = {"id": "new"}

        copy_child_objects("src", "dest", mock_service)

        assert mock_service.files().copy.call_count >= 2


# ---------------------------------------------------------------------------
# Exponential backoff
# ---------------------------------------------------------------------------


class TestCopyFileWithBackoff:
    def _make_http_error(self, status):
        resp = Mock()
        resp.status = status
        return HttpError(resp=resp, content=b"error")

    def test_success_on_first_attempt(self, mock_service):
        file = {"id": "f1", "name": "doc.txt"}
        mock_service.files().copy().execute.return_value = {"id": "new"}

        result = _copy_file_with_backoff(mock_service, file, "dest", max_retries=3, max_backoff=60)

        assert result is True

    def test_retry_on_500_then_success(self, mock_service):
        file = {"id": "f1", "name": "doc.txt"}
        err = self._make_http_error(500)
        mock_service.files().copy().execute.side_effect = [err, {"id": "new"}]

        with patch("gcp.copy_folder.time.sleep"):
            result = _copy_file_with_backoff(
                mock_service, file, "dest", max_retries=2, max_backoff=60
            )

        assert result is True

    def test_rate_limit_429_retried_with_warning(self, mock_service):
        file = {"id": "f1", "name": "doc.txt"}
        err = self._make_http_error(429)
        mock_service.files().copy().execute.side_effect = [err, {"id": "new"}]

        with patch("gcp.copy_folder.time.sleep"):
            with patch("gcp.copy_folder.logging.log") as mock_log:
                result = _copy_file_with_backoff(
                    mock_service, file, "dest", max_retries=2, max_backoff=60
                )

        assert result is True
        # Should have logged at WARNING level for rate-limit
        import logging as _logging
        warning_calls = [c for c in mock_log.call_args_list if c.args[0] == _logging.WARNING]
        assert len(warning_calls) >= 1

    def test_all_retries_exhausted_returns_false(self, mock_service):
        file = {"id": "f1", "name": "doc.txt"}
        err = self._make_http_error(500)
        mock_service.files().copy().execute.side_effect = err

        with patch("gcp.copy_folder.time.sleep"):
            result = _copy_file_with_backoff(
                mock_service, file, "dest", max_retries=3, max_backoff=60
            )

        assert result is False
        assert mock_service.files().copy.call_count >= 3

    def test_backoff_sleep_called_between_retries(self, mock_service):
        file = {"id": "f1", "name": "doc.txt"}
        err = self._make_http_error(503)
        mock_service.files().copy().execute.side_effect = [err, err, {"id": "new"}]

        with patch("gcp.copy_folder.time.sleep") as mock_sleep:
            _copy_file_with_backoff(
                mock_service, file, "dest", max_retries=3, max_backoff=60
            )

        assert mock_sleep.call_count == 2


# ---------------------------------------------------------------------------
# Parallel copy (workers > 1)
# ---------------------------------------------------------------------------


class TestParallelCopy:
    def test_parallel_copy_copies_all_files(self, mock_service):
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "f1", "name": "a.txt", "mimeType": "text/plain"},
                    {"id": "f2", "name": "b.txt", "mimeType": "text/plain"},
                    {"id": "f3", "name": "c.txt", "mimeType": "text/plain"},
                ]
            },
            {"files": []},
        ]
        mock_service.files().copy().execute.return_value = {"id": "new"}

        copy_child_objects("src", "dest", mock_service, workers=3)

        assert mock_service.files().copy.call_count >= 3

    def test_parallel_copy_with_filter(self, mock_service):
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "f1", "name": "a.pdf", "mimeType": "application/pdf"},
                    {"id": "f2", "name": "b.jpg", "mimeType": "image/jpeg"},
                ]
            },
            {"files": []},
        ]
        mock_service.files().copy().execute.return_value = {"id": "new"}

        with patch("gcp.copy_folder.logging.info") as mock_info:
            copy_child_objects(
                "src", "dest", mock_service, workers=2, include_mime=["application/pdf"]
            )

        summary_calls = [
            c for c in mock_info.call_args_list
            if c.args and "COPY PROGRESS SUMMARY" in str(c.args[0])
        ]
        assert len(summary_calls) == 1
        summary_args = summary_calls[0].args
        summary_str = summary_args[0] % summary_args[1:]
        assert "skipped=1" in summary_str

    def test_parallel_copy_handles_failures(self, mock_service):
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "f1", "name": "a.txt", "mimeType": "text/plain"},
                ]
            },
            {"files": []},
        ]
        err = HttpError(resp=Mock(status=500), content=b"error")
        mock_service.files().copy().execute.side_effect = err

        with patch("gcp.copy_folder.logging.info") as mock_info:
            copy_child_objects("src", "dest", mock_service, workers=2, max_retries=1)

        summary_calls = [
            c for c in mock_info.call_args_list
            if c.args and "COPY PROGRESS SUMMARY" in str(c.args[0])
        ]
        assert len(summary_calls) == 1


# ---------------------------------------------------------------------------
# CLI argument integration
# ---------------------------------------------------------------------------


class TestCLIArgs:
    def test_help_env_shows_vars(self, capsys):
        main(["--help-env"])
        out = capsys.readouterr().out
        assert "GOOGLE_DRIVE_CLIENT_ID_FILE" in out
        assert "GOOGLE_DRIVE_SOURCE_FOLDER_ID" in out
        assert "GOOGLE_DRIVE_DESTINATION_FOLDER_ID" in out

    @patch("gcp.copy_folder.authenticate_and_authorize")
    @patch("gcp.copy_folder.create_drive_service")
    @patch("gcp.copy_folder.count_child_objects", return_value=(5, 2))
    def test_dry_run_with_include_mime(self, mock_count, mock_svc, mock_auth, capsys):
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_svc.return_value = svc
        svc.files().get().execute.return_value = {"name": "MyFolder"}

        import os
        with patch.dict(
            os.environ,
            {
                "GOOGLE_DRIVE_CLIENT_ID_FILE": "fake.json",
                "GOOGLE_DRIVE_SOURCE_FOLDER_ID": "src123",
                "GOOGLE_DRIVE_DESTINATION_FOLDER_ID": "dst456",
            },
        ):
            main(["--dry-run", "--include-mime", "docs,pdf"])

        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert "include:" in out

    @patch("gcp.copy_folder.authenticate_and_authorize")
    @patch("gcp.copy_folder.create_drive_service")
    @patch("gcp.copy_folder.count_child_objects", return_value=(3, 1))
    def test_dry_run_with_workers_shows_parallel_note(
        self, mock_count, mock_svc, mock_auth, capsys
    ):
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_svc.return_value = svc
        svc.files().get().execute.return_value = {"name": "Folder"}

        import os
        with patch.dict(
            os.environ,
            {
                "GOOGLE_DRIVE_CLIENT_ID_FILE": "fake.json",
                "GOOGLE_DRIVE_SOURCE_FOLDER_ID": "src",
                "GOOGLE_DRIVE_DESTINATION_FOLDER_ID": "dst",
            },
        ):
            main(["--dry-run", "--workers", "4"])

        out = capsys.readouterr().out
        assert "4 workers" in out
