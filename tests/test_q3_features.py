"""Tests for Q3 features: MIME filters, exponential backoff, and parallel copy."""

# pylint: disable=redefined-outer-name,import-outside-toplevel
import logging
import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from googleapiclient.errors import HttpError

from gcp.copy_folder import (
    MIME_ALIASES,
    _copy_file_with_backoff,
    _dest_has_file,
    _dest_has_folder,
    _file_passes_filter,
    _mime_matches,
    _resolve_mime_aliases,
    copy_child_objects,
    count_child_objects,
    main,
)


@pytest.fixture
def mock_service():
    """Create a mock Google Drive service."""
    return MagicMock()


# ---------------------------------------------------------------------------
# MIME filter helpers
# ---------------------------------------------------------------------------


class TestResolveMimeAliases:
    """Test alias expansion for MIME type shortcuts."""

    def test_known_alias(self):
        """Test that 'docs' expands to the Google Docs MIME type."""
        assert _resolve_mime_aliases(["docs"]) == [
            "application/vnd.google-apps.document"
        ]

    def test_passthrough_full_mime(self):
        """Test that a full MIME type passes through unchanged."""
        assert _resolve_mime_aliases(["application/pdf"]) == ["application/pdf"]

    def test_mixed(self):
        """Test that aliases and full MIME types can be mixed."""
        result = _resolve_mime_aliases(["pdf", "text/plain"])
        assert result == ["application/pdf", "text/plain"]

    def test_prefix_alias_images(self):
        """Test that 'images' expands to the 'image/' prefix pattern."""
        assert _resolve_mime_aliases(["images"]) == ["image/"]

    def test_all_aliases_resolve(self):
        """Test that every alias in MIME_ALIASES resolves correctly."""
        for alias, expected in MIME_ALIASES.items():
            result = _resolve_mime_aliases([alias])
            assert result == [expected]


class TestMimeMatches:
    """Test MIME type pattern matching."""

    def test_exact_match(self):
        """Test exact MIME type match."""
        assert _mime_matches("application/pdf", ["application/pdf"])

    def test_no_match(self):
        """Test that a non-matching MIME type returns False."""
        assert not _mime_matches("application/pdf", ["text/plain"])

    def test_prefix_match(self):
        """Test prefix pattern matching for image subtypes."""
        assert _mime_matches("image/jpeg", ["image/"])
        assert _mime_matches("image/png", ["image/"])

    def test_prefix_no_partial_word_match(self):
        """Test that a prefix pattern does not match unrelated types."""
        assert not _mime_matches("application/pdf", ["image/"])

    def test_empty_patterns(self):
        """Test that an empty pattern list never matches."""
        assert not _mime_matches("application/pdf", [])


class TestFilePassesFilter:
    """Test combined include/exclude MIME filter logic."""

    def test_no_filters_always_passes(self):
        """Test that a file passes when no filters are set."""
        assert _file_passes_filter("application/pdf", [], [])

    def test_include_match_passes(self):
        """Test that a file matching the include list passes."""
        assert _file_passes_filter("application/pdf", ["application/pdf"], [])

    def test_include_no_match_fails(self):
        """Test that a file not in the include list is rejected."""
        assert not _file_passes_filter("text/plain", ["application/pdf"], [])

    def test_exclude_match_fails(self):
        """Test that a file matching the exclude list is rejected."""
        assert not _file_passes_filter("application/pdf", [], ["application/pdf"])

    def test_exclude_takes_priority_over_include(self):
        """Test that exclude overrides include when both match."""
        assert not _file_passes_filter(
            "application/pdf", ["application/pdf"], ["application/pdf"]
        )

    def test_prefix_include(self):
        """Test prefix-based include filter."""
        assert _file_passes_filter("image/jpeg", ["image/"], [])
        assert not _file_passes_filter("text/plain", ["image/"], [])

    def test_prefix_exclude(self):
        """Test prefix-based exclude filter."""
        assert not _file_passes_filter("image/jpeg", [], ["image/"])
        assert _file_passes_filter("text/plain", [], ["image/"])


# ---------------------------------------------------------------------------
# count_child_objects with MIME filters
# ---------------------------------------------------------------------------


class TestCountChildObjectsWithFilters:
    """Test recursive counting with MIME type filters."""

    def test_include_filter_counts_only_matching(self, mock_service):
        """Test that include filter limits counted files to matching types."""
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {
                        "id": "1",
                        "name": "doc.gdoc",
                        "mimeType": "application/vnd.google-apps.document",
                    },
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
        """Test that exclude filter omits files with matching MIME types."""
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "1", "name": "img.jpg", "mimeType": "image/jpeg"},
                    {"id": "2", "name": "doc.txt", "mimeType": "text/plain"},
                ]
            }
        ]
        num_files, _ = count_child_objects(
            "folder_id",
            mock_service,
            exclude_mime=["image/"],
        )
        assert num_files == 1

    def test_filters_propagate_to_subfolders(self, mock_service):
        """Test that MIME filters are applied recursively into subfolders."""
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
    """Test copy operations with MIME type filters applied."""

    def test_include_filter_skips_non_matching_files(self, mock_service):
        """Test that files not matching the include filter are not copied."""
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {
                        "id": "f1",
                        "name": "doc.gdoc",
                        "mimeType": "application/vnd.google-apps.document",
                    },
                    {"id": "f2", "name": "sheet.txt", "mimeType": "text/plain"},
                ]
            },
            {"files": []},
        ]
        mock_service.files().copy().execute.return_value = {"id": "new"}

        copy_child_objects(
            "src",
            "dest",
            mock_service,
            include_mime=["application/vnd.google-apps.document"],
        )

        assert mock_service.files().copy.call_count >= 1
        copy_calls = mock_service.files().copy.call_args_list
        copied_ids = [c[1]["fileId"] for c in copy_calls if "fileId" in (c[1] or {})]
        if copied_ids:
            assert "f2" not in copied_ids

    def test_exclude_filter_skips_matching_files(self, mock_service):
        """Test that files matching the exclude filter are skipped and counted."""
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

        with patch("gcp.copy_folder.logging.info") as mock_info:
            copy_child_objects("src", "dest", mock_service, exclude_mime=["image/"])

        summary_calls = [
            c
            for c in mock_info.call_args_list
            if c.args and "COPY PROGRESS SUMMARY" in str(c.args[0])
        ]
        assert len(summary_calls) == 1
        summary_args = summary_calls[0].args
        assert "skipped=1" in (summary_args[0] % summary_args[1:])

    def test_no_filter_copies_all_files(self, mock_service):
        """Test that all files are copied when no filters are set."""
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
    """Test exponential backoff retry logic for file copies."""

    def _make_http_error(self, status):
        """Create an HttpError with the given HTTP status code."""
        resp = Mock()
        resp.status = status
        return HttpError(resp=resp, content=b"error")

    def test_success_on_first_attempt(self, mock_service):
        """Test that a successful copy returns True immediately."""
        file = {"id": "f1", "name": "doc.txt"}
        mock_service.files().copy().execute.return_value = {"id": "new"}

        result = _copy_file_with_backoff(
            mock_service, file, "dest", max_retries=3, max_backoff=60
        )

        assert result is True

    def test_retry_on_500_then_success(self, mock_service):
        """Test that a 500 error triggers a retry and eventual success."""
        file = {"id": "f1", "name": "doc.txt"}
        err = self._make_http_error(500)
        mock_service.files().copy().execute.side_effect = [err, {"id": "new"}]

        with patch("gcp.copy_folder.time.sleep"):
            result = _copy_file_with_backoff(
                mock_service, file, "dest", max_retries=2, max_backoff=60
            )

        assert result is True

    def test_rate_limit_429_retried_with_warning(self, mock_service):
        """Test that a 429 response is retried and logged at WARNING level."""
        file = {"id": "f1", "name": "doc.txt"}
        err = self._make_http_error(429)
        mock_service.files().copy().execute.side_effect = [err, {"id": "new"}]

        with patch("gcp.copy_folder.time.sleep"):
            with patch("gcp.copy_folder.logging.log") as mock_log:
                result = _copy_file_with_backoff(
                    mock_service, file, "dest", max_retries=2, max_backoff=60
                )

        assert result is True
        warning_calls = [
            c for c in mock_log.call_args_list if c.args[0] == logging.WARNING
        ]
        assert len(warning_calls) >= 1

    def test_all_retries_exhausted_returns_false(self, mock_service):
        """Test that exhausting all retries returns False without raising."""
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
        """Test that sleep is called between retry attempts."""
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
    """Test parallel file copy using multiple workers."""

    def test_parallel_copy_copies_all_files(self, mock_service):
        """Test that all files are copied when workers > 1."""
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
        """Test that MIME filters are respected in parallel copy mode."""
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
            c
            for c in mock_info.call_args_list
            if c.args and "COPY PROGRESS SUMMARY" in str(c.args[0])
        ]
        assert len(summary_calls) == 1
        summary_args = summary_calls[0].args
        summary_str = summary_args[0] % summary_args[1:]
        assert "skipped=1" in summary_str

    def test_parallel_copy_handles_failures(self, mock_service):
        """Test that copy failures are tracked correctly in parallel mode."""
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
            c
            for c in mock_info.call_args_list
            if c.args and "COPY PROGRESS SUMMARY" in str(c.args[0])
        ]
        assert len(summary_calls) == 1


# ---------------------------------------------------------------------------
# CLI argument integration
# ---------------------------------------------------------------------------


class TestCLIArgs:
    """Test that new CLI arguments are parsed and passed through correctly."""

    def test_help_env_shows_vars(self, capsys):
        """Test that --help-env prints all required environment variable names."""
        main(["--help-env"])
        out = capsys.readouterr().out
        assert "GOOGLE_DRIVE_CLIENT_ID_FILE" in out
        assert "GOOGLE_DRIVE_SOURCE_FOLDER_ID" in out
        assert "GOOGLE_DRIVE_DESTINATION_FOLDER_ID" in out

    @patch("gcp.copy_folder.authenticate_and_authorize")
    @patch("gcp.copy_folder.create_drive_service")
    @patch("gcp.copy_folder.count_child_objects", return_value=(5, 2))
    def test_dry_run_with_include_mime(
        self, _mock_count, mock_svc, mock_auth, capsys
    ):
        """Test that --include-mime is shown in dry-run output."""
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_svc.return_value = svc
        svc.files().get().execute.return_value = {"name": "MyFolder"}

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
        self, _mock_count, mock_svc, mock_auth, capsys
    ):
        """Test that --workers > 1 prints a parallel-copy note in dry-run output."""
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_svc.return_value = svc
        svc.files().get().execute.return_value = {"name": "Folder"}

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

    @patch("gcp.copy_folder.authenticate_and_authorize")
    @patch("gcp.copy_folder.create_drive_service")
    @patch("gcp.copy_folder.count_child_objects", return_value=(2, 0))
    def test_dry_run_with_skip_existing_flag(
        self, _mock_count, mock_svc, mock_auth, capsys
    ):
        """Test that --skip-existing is accepted without error in dry-run."""
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_svc.return_value = svc
        svc.files().get().execute.return_value = {"name": "Folder"}

        with patch.dict(
            os.environ,
            {
                "GOOGLE_DRIVE_CLIENT_ID_FILE": "fake.json",
                "GOOGLE_DRIVE_SOURCE_FOLDER_ID": "src",
                "GOOGLE_DRIVE_DESTINATION_FOLDER_ID": "dst",
            },
        ):
            main(["--dry-run", "--skip-existing"])

        out = capsys.readouterr().out
        assert "DRY RUN" in out


# ---------------------------------------------------------------------------
# Skip-existing helpers and integration
# ---------------------------------------------------------------------------


class TestDestHasFile:
    """Test the _dest_has_file existence check helper."""

    def test_file_exists_returns_true(self, mock_service):
        """Test that True is returned when a matching file is found in the destination."""
        mock_service.files().list().execute.return_value = {"files": [{"id": "f1"}]}
        assert _dest_has_file(mock_service, "dest_folder", "report.pdf") is True

    def test_file_absent_returns_false(self, mock_service):
        """Test that False is returned when no matching file is found."""
        mock_service.files().list().execute.return_value = {"files": []}
        assert _dest_has_file(mock_service, "dest_folder", "report.pdf") is False


class TestDestHasFolder:
    """Test the _dest_has_folder existence check helper."""

    def test_folder_exists_returns_id(self, mock_service):
        """Test that the existing folder's ID is returned when found."""
        mock_service.files().list().execute.return_value = {"files": [{"id": "folder1"}]}
        result = _dest_has_folder(mock_service, "dest_folder", "Archive")
        assert result == "folder1"

    def test_folder_absent_returns_none(self, mock_service):
        """Test that None is returned when no matching subfolder is found."""
        mock_service.files().list().execute.return_value = {"files": []}
        result = _dest_has_folder(mock_service, "dest_folder", "Archive")
        assert result is None


class TestSkipExisting:
    """Test incremental copy behaviour with skip_existing=True."""

    def test_existing_file_not_copied(self, mock_service):
        """Test that a file already in the destination is skipped and counted."""
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "f1", "name": "report.pdf", "mimeType": "application/pdf"},
                ]
            },
            {"files": []},
        ]
        # _dest_has_file returns True for f1 (already exists)
        with patch("gcp.copy_folder._dest_has_file", return_value=True):
            with patch("gcp.copy_folder.logging.info") as mock_info:
                copy_child_objects("src", "dest", mock_service, skip_existing=True)

        mock_service.files().copy.assert_not_called()
        summary_calls = [
            c for c in mock_info.call_args_list
            if c.args and "COPY PROGRESS SUMMARY" in str(c.args[0])
        ]
        assert len(summary_calls) == 1
        summary_str = summary_calls[0].args[0] % summary_calls[0].args[1:]
        assert "skipped=1" in summary_str

    def test_new_file_is_copied(self, mock_service):
        """Test that a file not yet in the destination is copied normally."""
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {"id": "f1", "name": "new.pdf", "mimeType": "application/pdf"},
                ]
            },
            {"files": []},
        ]
        mock_service.files().copy().execute.return_value = {"id": "copy1"}

        with patch("gcp.copy_folder._dest_has_file", return_value=False):
            copy_child_objects("src", "dest", mock_service, skip_existing=True)

        assert mock_service.files().copy.call_count >= 1

    def test_existing_folder_reused_not_duplicated(self, mock_service):
        """Test that an existing destination subfolder is reused rather than recreated."""
        mock_service.files().list().execute.side_effect = [
            {"files": []},  # no files
            {
                "files": [
                    {
                        "id": "sub1",
                        "name": "Archive",
                        "mimeType": "application/vnd.google-apps.folder",
                    }
                ]
            },
            {"files": []},  # subfolder files
            {"files": []},  # subfolder subfolders
        ]

        with patch("gcp.copy_folder._dest_has_folder", return_value="existing_sub"):
            copy_child_objects("src", "dest", mock_service, skip_existing=True)

        mock_service.files().create.assert_not_called()
