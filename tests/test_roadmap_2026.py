"""
Tests for the 2026 Q4 roadmap features: duplicate-detection report and
--mirror-permissions.
"""
# pylint: disable=redefined-outer-name
import csv
import os
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest
from googleapiclient.errors import HttpError

from gcp.copy_folder import (
    NON_MIRRORABLE_ROLES,
    _copy_file_with_backoff,
    _copy_permissions,
    _list_files_recursive,
    copy_child_objects,
    find_duplicate_files,
    main,
    write_duplicate_report,
)


@pytest.fixture
def mock_service():
    """Create a mock Google Drive service."""
    return MagicMock()


# ---------------------------------------------------------------------------
# _list_files_recursive
# ---------------------------------------------------------------------------


class TestListFilesRecursive:
    """Test the recursive file-listing helper used by duplicate detection."""

    def test_flat_folder(self, mock_service):
        """Test that files directly in the folder are listed with their path."""
        mock_service.files().list().execute.return_value = {
            "files": [
                {"id": "f1", "name": "a.txt", "mimeType": "text/plain", "size": "100"},
                {"id": "f2", "name": "b.pdf", "mimeType": "application/pdf", "size": "200"},
            ]
        }
        result = _list_files_recursive("root", mock_service)
        assert len(result) == 2
        names = {f["name"] for f in result}
        assert names == {"a.txt", "b.pdf"}
        assert all(f["path"] in ("a.txt", "b.pdf") for f in result)

    def test_recurses_into_subfolders(self, mock_service):
        """Test that files nested in subfolders are found with a prefixed path."""
        mock_service.files().list().execute.side_effect = [
            {
                "files": [
                    {
                        "id": "sub",
                        "name": "Sub",
                        "mimeType": "application/vnd.google-apps.folder",
                    }
                ]
            },
            {
                "files": [
                    {"id": "f1", "name": "nested.txt", "mimeType": "text/plain", "size": "50"},
                ]
            },
        ]
        result = _list_files_recursive("root", mock_service)
        assert len(result) == 1
        assert result[0]["path"] == "Sub/nested.txt"

    def test_google_native_file_has_no_size(self, mock_service):
        """Test that a Google Doc (no size field) is reported with size=None."""
        mock_service.files().list().execute.return_value = {
            "files": [
                {
                    "id": "f1",
                    "name": "Doc",
                    "mimeType": "application/vnd.google-apps.document",
                }
            ]
        }
        result = _list_files_recursive("root", mock_service)
        assert result[0]["size"] is None


# ---------------------------------------------------------------------------
# find_duplicate_files
# ---------------------------------------------------------------------------


class TestFindDuplicateFiles:
    """Test cross-tree duplicate detection by name + size."""

    def test_matching_name_and_size_is_duplicate(self, mock_service):
        """Test that a same-name, same-size file in both trees is reported."""
        mock_service.files().list().execute.side_effect = [
            {"files": [{"id": "s1", "name": "report.pdf", "mimeType": "application/pdf", "size": "1000"}]},
            {"files": [{"id": "d1", "name": "report.pdf", "mimeType": "application/pdf", "size": "1000"}]},
        ]
        duplicates = find_duplicate_files("src", "dest", mock_service)
        assert len(duplicates) == 1
        assert duplicates[0]["name"] == "report.pdf"
        assert duplicates[0]["size"] == "1000"
        assert duplicates[0]["source_path"] == "report.pdf"
        assert duplicates[0]["destination_path"] == "report.pdf"

    def test_same_name_different_size_not_duplicate(self, mock_service):
        """Test that same name but different size is not reported as a duplicate."""
        mock_service.files().list().execute.side_effect = [
            {"files": [{"id": "s1", "name": "report.pdf", "mimeType": "application/pdf", "size": "1000"}]},
            {"files": [{"id": "d1", "name": "report.pdf", "mimeType": "application/pdf", "size": "2000"}]},
        ]
        duplicates = find_duplicate_files("src", "dest", mock_service)
        assert not duplicates

    def test_different_name_same_size_not_duplicate(self, mock_service):
        """Test that different names with the same size are not reported."""
        mock_service.files().list().execute.side_effect = [
            {"files": [{"id": "s1", "name": "a.pdf", "mimeType": "application/pdf", "size": "1000"}]},
            {"files": [{"id": "d1", "name": "b.pdf", "mimeType": "application/pdf", "size": "1000"}]},
        ]
        duplicates = find_duplicate_files("src", "dest", mock_service)
        assert not duplicates

    def test_google_native_files_excluded_from_matching(self, mock_service):
        """Test that same-name Google Docs (no size) are never reported as duplicates."""
        mock_service.files().list().execute.side_effect = [
            {"files": [{"id": "s1", "name": "Notes", "mimeType": "application/vnd.google-apps.document"}]},
            {"files": [{"id": "d1", "name": "Notes", "mimeType": "application/vnd.google-apps.document"}]},
        ]
        duplicates = find_duplicate_files("src", "dest", mock_service)
        assert not duplicates

    def test_no_overlap_returns_empty(self, mock_service):
        """Test that entirely disjoint trees produce no duplicates."""
        mock_service.files().list().execute.side_effect = [
            {"files": [{"id": "s1", "name": "only-src.txt", "mimeType": "text/plain", "size": "10"}]},
            {"files": [{"id": "d1", "name": "only-dest.txt", "mimeType": "text/plain", "size": "10"}]},
        ]
        duplicates = find_duplicate_files("src", "dest", mock_service)
        assert not duplicates


# ---------------------------------------------------------------------------
# write_duplicate_report
# ---------------------------------------------------------------------------


class TestWriteDuplicateReport:
    """Test CSV output of the duplicate report."""

    def test_writes_header_and_rows(self, tmp_path):
        """Test that the CSV file has the expected header and row content."""
        duplicates = [
            {"name": "a.pdf", "size": "1000", "source_path": "a.pdf", "destination_path": "a.pdf"},
        ]
        out_path = str(tmp_path / "duplicate-report.csv")
        result_path = write_duplicate_report(duplicates, out_path)
        assert result_path == out_path

        with open(out_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["File Name", "Size (bytes)", "Source Path", "Destination Path"]
        assert rows[1] == ["a.pdf", "1000", "a.pdf", "a.pdf"]

    def test_empty_duplicates_writes_header_only(self, tmp_path):
        """Test that an empty duplicate list still writes a valid header-only CSV."""
        out_path = str(tmp_path / "duplicate-report.csv")
        write_duplicate_report([], out_path)
        with open(out_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert len(rows) == 1

    def test_creates_missing_output_directory(self, tmp_path):
        """Test that write_duplicate_report creates the parent directory if missing."""
        out_path = str(tmp_path / "nested" / "dir" / "duplicate-report.csv")
        write_duplicate_report([], out_path)
        assert os.path.isfile(out_path)


# ---------------------------------------------------------------------------
# _copy_permissions
# ---------------------------------------------------------------------------


class TestCopyPermissions:
    """Test mirroring of sharing/ACL permissions from source to destination."""

    def test_user_permission_is_mirrored(self, mock_service):
        """Test that a 'user' role/type permission is recreated on the destination."""
        mock_service.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "role": "writer", "type": "user", "emailAddress": "a@example.com"}
            ]
        }
        _copy_permissions(mock_service, "src_id", "dest_id")

        mock_service.permissions().create.assert_called_once()
        _, kwargs = mock_service.permissions().create.call_args
        assert kwargs["fileId"] == "dest_id"
        assert kwargs["body"] == {"role": "writer", "type": "user", "emailAddress": "a@example.com"}
        assert kwargs["sendNotificationEmail"] is False

    def test_owner_role_is_never_mirrored(self, mock_service):
        """Test that an 'owner' permission is skipped entirely."""
        assert "owner" in NON_MIRRORABLE_ROLES
        mock_service.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "role": "owner", "type": "user", "emailAddress": "owner@example.com"}
            ]
        }
        _copy_permissions(mock_service, "src_id", "dest_id")
        mock_service.permissions().create.assert_not_called()

    def test_domain_permission_is_mirrored(self, mock_service):
        """Test that a 'domain' type permission carries the domain field."""
        mock_service.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "role": "reader", "type": "domain", "domain": "example.com"}
            ]
        }
        _copy_permissions(mock_service, "src_id", "dest_id")
        _, kwargs = mock_service.permissions().create.call_args
        assert kwargs["body"] == {"role": "reader", "type": "domain", "domain": "example.com"}

    def test_anyone_permission_is_mirrored(self, mock_service):
        """Test that an 'anyone' type permission carries allowFileDiscovery."""
        mock_service.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "role": "reader", "type": "anyone", "allowFileDiscovery": False}
            ]
        }
        _copy_permissions(mock_service, "src_id", "dest_id")
        _, kwargs = mock_service.permissions().create.call_args
        assert kwargs["body"] == {"role": "reader", "type": "anyone", "allowFileDiscovery": False}

    def test_permission_missing_required_field_is_skipped(self, mock_service):
        """Test that a malformed permission (e.g. user with no email) is skipped."""
        mock_service.permissions().list().execute.return_value = {
            "permissions": [{"id": "p1", "role": "writer", "type": "user"}]
        }
        _copy_permissions(mock_service, "src_id", "dest_id")
        mock_service.permissions().create.assert_not_called()

    def test_list_failure_is_logged_and_does_not_raise(self, mock_service):
        """Test that a permissions().list() failure is handled gracefully."""
        err = HttpError(resp=Mock(status=403), content=b"forbidden")
        mock_service.permissions().list().execute.side_effect = err
        _copy_permissions(mock_service, "src_id", "dest_id")  # should not raise
        mock_service.permissions().create.assert_not_called()

    def test_create_failure_does_not_raise_and_continues(self, mock_service):
        """Test that a single failed permissions().create() doesn't abort remaining ones."""
        mock_service.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "role": "writer", "type": "user", "emailAddress": "a@example.com"},
                {"id": "p2", "role": "reader", "type": "user", "emailAddress": "b@example.com"},
            ]
        }
        err = HttpError(resp=Mock(status=400), content=b"bad request")
        mock_service.permissions().create.return_value.execute.side_effect = [err, {"id": "ok"}]
        _copy_permissions(mock_service, "src_id", "dest_id")  # should not raise
        assert mock_service.permissions().create.call_count == 2


# ---------------------------------------------------------------------------
# _copy_file_with_backoff + mirror_permissions
# ---------------------------------------------------------------------------


class TestCopyFileWithBackoffMirrorsPermissions:
    """Test that mirror_permissions triggers ACL copy after a successful file copy."""

    def test_mirror_permissions_called_on_success(self, mock_service):
        """Test that _copy_permissions is invoked with source/destination IDs."""
        file = {"id": "src_file_id", "name": "doc.txt"}
        mock_service.files().copy().execute.return_value = {"id": "new_file_id"}

        with patch("gcp.copy_folder._copy_permissions") as mock_mirror:
            result = _copy_file_with_backoff(
                mock_service, file, "dest", max_retries=1, max_backoff=10,
                mirror_permissions=True,
            )

        assert result is True
        mock_mirror.assert_called_once_with(mock_service, "src_file_id", "new_file_id")

    def test_mirror_permissions_not_called_by_default(self, mock_service):
        """Test that permissions are not mirrored unless explicitly requested."""
        file = {"id": "src_file_id", "name": "doc.txt"}
        mock_service.files().copy().execute.return_value = {"id": "new_file_id"}

        with patch("gcp.copy_folder._copy_permissions") as mock_mirror:
            _copy_file_with_backoff(
                mock_service, file, "dest", max_retries=1, max_backoff=10
            )

        mock_mirror.assert_not_called()

    def test_mirror_permissions_not_called_on_failure(self, mock_service):
        """Test that permissions are not mirrored when the copy never succeeds."""
        file = {"id": "src_file_id", "name": "doc.txt"}
        err = HttpError(resp=Mock(status=500), content=b"error")
        mock_service.files().copy().execute.side_effect = err

        with patch("gcp.copy_folder.time.sleep"):
            with patch("gcp.copy_folder._copy_permissions") as mock_mirror:
                result = _copy_file_with_backoff(
                    mock_service, file, "dest", max_retries=2, max_backoff=10,
                    mirror_permissions=True,
                )

        assert result is False
        mock_mirror.assert_not_called()


# ---------------------------------------------------------------------------
# copy_child_objects + mirror_permissions integration
# ---------------------------------------------------------------------------


class TestCopyChildObjectsMirrorPermissions:
    """Test end-to-end mirror_permissions wiring through copy_child_objects."""

    def test_mirrors_permissions_on_copied_file_and_created_folder(self, mock_service):
        """Test that both a copied file and a newly created folder get mirrored permissions."""
        mock_service.files().list().execute.side_effect = [
            {"files": [{"id": "f1", "name": "a.txt", "mimeType": "text/plain"}]},  # files
            {
                "files": [
                    {"id": "sub", "name": "Sub", "mimeType": "application/vnd.google-apps.folder"}
                ]
            },  # folders
            {"files": []},  # recursion into Sub: files
            {"files": []},  # recursion into Sub: folders
        ]
        mock_service.files().copy().execute.return_value = {"id": "new_file"}
        mock_service.files().create().execute.return_value = {"id": "new_folder"}

        with patch("gcp.copy_folder._copy_permissions") as mock_mirror:
            copy_child_objects("src", "dest", mock_service, mirror_permissions=True)

        mock_mirror.assert_any_call(mock_service, "f1", "new_file")
        mock_mirror.assert_any_call(mock_service, "sub", "new_folder")
        assert mock_mirror.call_count == 2

    def test_no_mirroring_when_disabled(self, mock_service):
        """Test that _copy_permissions is never called when mirror_permissions=False."""
        mock_service.files().list().execute.side_effect = [
            {"files": [{"id": "f1", "name": "a.txt", "mimeType": "text/plain"}]},
            {"files": []},
        ]
        mock_service.files().copy().execute.return_value = {"id": "new_file"}

        with patch("gcp.copy_folder._copy_permissions") as mock_mirror:
            copy_child_objects("src", "dest", mock_service)

        mock_mirror.assert_not_called()

    def test_skip_existing_reused_folder_not_mirrored(self, mock_service):
        """Test that reusing an existing destination folder (skip_existing) does not mirror permissions."""
        mock_service.files().list().execute.side_effect = [
            {"files": []},
            {
                "files": [
                    {"id": "sub", "name": "Archive", "mimeType": "application/vnd.google-apps.folder"}
                ]
            },
            {"files": []},
            {"files": []},
        ]
        with patch("gcp.copy_folder._dest_has_folder", return_value="existing_sub"):
            with patch("gcp.copy_folder._copy_permissions") as mock_mirror:
                copy_child_objects(
                    "src", "dest", mock_service, skip_existing=True, mirror_permissions=True
                )
        mock_mirror.assert_not_called()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLIDuplicateReport:
    """Test the --duplicate-report CLI mode."""

    @patch("gcp.copy_folder.authenticate_and_authorize")
    @patch("gcp.copy_folder.create_drive_service")
    @patch("gcp.copy_folder.find_duplicate_files")
    @patch("gcp.copy_folder.write_duplicate_report")
    @patch("gcp.copy_folder.count_child_objects")
    @patch("gcp.copy_folder.copy_child_objects")
    def test_duplicate_report_mode_skips_copy(
        self, mock_copy, mock_count, mock_write, mock_find, mock_create_service, mock_auth
    ):
        """Test that --duplicate-report writes the report and returns without copying."""
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_create_service.return_value = svc
        svc.files().get().execute.side_effect = [{"name": "Source"}, {"name": "Dest"}]
        mock_find.return_value = [{"name": "a.pdf", "size": "10", "source_path": "a.pdf", "destination_path": "a.pdf"}]
        mock_write.return_value = "./outputs/duplicate-report.csv"

        with patch.dict(
            os.environ,
            {
                "GOOGLE_DRIVE_CLIENT_ID_FILE": "fake.json",
                "GOOGLE_DRIVE_SOURCE_FOLDER_ID": "src123",
                "GOOGLE_DRIVE_DESTINATION_FOLDER_ID": "dst456",
            },
        ):
            main(["--duplicate-report"])

        mock_find.assert_called_once_with("src123", "dst456", svc)
        mock_write.assert_called_once_with(mock_find.return_value)
        mock_copy.assert_not_called()
        mock_count.assert_not_called()

    @patch("gcp.copy_folder.authenticate_and_authorize")
    @patch("gcp.copy_folder.create_drive_service")
    @patch("gcp.copy_folder.find_duplicate_files")
    @patch("gcp.copy_folder.write_duplicate_report")
    def test_duplicate_report_prints_summary(
        self, mock_write, mock_find, mock_create_service, mock_auth, capsys
    ):
        """Test that the duplicate count and report path are printed."""
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_create_service.return_value = svc
        svc.files().get().execute.side_effect = [{"name": "Source"}, {"name": "Dest"}]
        mock_find.return_value = [{"name": "a.pdf"}, {"name": "b.pdf"}]
        mock_write.return_value = "./outputs/duplicate-report.csv"

        with patch.dict(
            os.environ,
            {
                "GOOGLE_DRIVE_CLIENT_ID_FILE": "fake.json",
                "GOOGLE_DRIVE_SOURCE_FOLDER_ID": "src",
                "GOOGLE_DRIVE_DESTINATION_FOLDER_ID": "dst",
            },
        ):
            main(["--duplicate-report"])

        out = capsys.readouterr().out
        assert "2 matching file(s) found" in out
        assert "./outputs/duplicate-report.csv" in out


class TestCLIMirrorPermissions:
    """Test the --mirror-permissions CLI flag."""

    @patch("gcp.copy_folder.authenticate_and_authorize")
    @patch("gcp.copy_folder.create_drive_service")
    @patch("gcp.copy_folder.count_child_objects", return_value=(3, 1))
    def test_dry_run_shows_mirror_permissions_note(
        self, _mock_count, mock_svc, mock_auth, capsys
    ):
        """Test that --mirror-permissions is noted in dry-run output."""
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
            main(["--dry-run", "--mirror-permissions"])

        out = capsys.readouterr().out
        assert "Permission mirroring enabled" in out

    @patch("gcp.copy_folder.authenticate_and_authorize")
    @patch("gcp.copy_folder.create_drive_service")
    @patch("gcp.copy_folder.count_child_objects", return_value=(1, 0))
    @patch("gcp.copy_folder.add_child_folders")
    @patch("gcp.copy_folder.copy_child_objects")
    @patch("gcp.copy_folder.compare_csv_files")
    @patch("builtins.open", new_callable=mock_open)
    def test_full_run_passes_mirror_permissions_flag(
        self,
        _mock_open,
        _mock_compare,
        mock_copy,
        _mock_add_child,
        _mock_count,
        mock_svc,
        mock_auth,
    ):
        """Test that a full (non-dry-run) invocation forwards mirror_permissions=True."""
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_svc.return_value = svc
        svc.files().get().execute.side_effect = [{"name": "Source"}, {"name": "Dest"}]

        with patch.dict(
            os.environ,
            {
                "GOOGLE_DRIVE_CLIENT_ID_FILE": "fake.json",
                "GOOGLE_DRIVE_SOURCE_FOLDER_ID": "src",
                "GOOGLE_DRIVE_DESTINATION_FOLDER_ID": "dst",
            },
        ):
            main(["--mirror-permissions"])

        assert mock_copy.call_count == 1
        _, kwargs = mock_copy.call_args
        assert kwargs["mirror_permissions"] is True
