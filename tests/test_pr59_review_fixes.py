"""
Tests for the CodeRabbit review findings on PR #59: permission pagination,
expirationTime preservation, sendNotificationEmail scoping, rate-limit
retry, CSV injection escaping, and CLI-boundary HttpError handling.
"""
# pylint: disable=redefined-outer-name
import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from googleapiclient.errors import HttpError

from gcp.copy_folder import _copy_permissions, _csv_safe, _list_files_recursive, main
from gcp.retry import call_with_rate_limit_retry


@pytest.fixture
def mock_service():
    """Create a mock Google Drive service."""
    return MagicMock()


def _rate_limit_error():
    return HttpError(resp=Mock(status=429), content=b"rate limited")


def _forbidden_error():
    return HttpError(resp=Mock(status=403), content=b"forbidden")


# ---------------------------------------------------------------------------
# call_with_rate_limit_retry (gcp/retry.py)
# ---------------------------------------------------------------------------
class TestCallWithRateLimitRetry:
    """Test the shared Drive-request retry helper."""

    def test_succeeds_after_transient_rate_limit(self):
        """Test that a 429 followed by success returns the successful result."""
        request = MagicMock()
        request().execute.side_effect = [_rate_limit_error(), {"ok": True}]

        with patch("time.sleep"):
            result = call_with_rate_limit_retry(request, max_retries=3, max_backoff=1.0)

        assert result == {"ok": True}
        assert request().execute.call_count == 2

    def test_non_rate_limit_error_raises_immediately(self):
        """Test that a 403 is not retried."""
        request = MagicMock()
        request().execute.side_effect = _forbidden_error()

        with pytest.raises(HttpError):
            call_with_rate_limit_retry(request, max_retries=3, max_backoff=1.0)

        assert request().execute.call_count == 1

    def test_rate_limit_exhausts_retries_and_raises(self):
        """Test that a persistent 429 is eventually re-raised, not swallowed."""
        request = MagicMock()
        request().execute.side_effect = _rate_limit_error()

        with patch("time.sleep"), pytest.raises(HttpError):
            call_with_rate_limit_retry(request, max_retries=2, max_backoff=1.0)

        assert request().execute.call_count == 2


# ---------------------------------------------------------------------------
# _copy_permissions: pagination, expirationTime, sendNotificationEmail, retry
# ---------------------------------------------------------------------------
class TestCopyPermissionsReviewFixes:
    """Test the correctness/security fixes applied to _copy_permissions."""

    def test_processes_every_permissions_page(self, mock_service):
        """Test that a paginated permissions.list response is fully consumed."""
        mock_service.permissions().list().execute.side_effect = [
            {
                "nextPageToken": "page2",
                "permissions": [
                    {"id": "p1", "role": "writer", "type": "user", "emailAddress": "a@example.com"}
                ],
            },
            {
                "permissions": [
                    {"id": "p2", "role": "reader", "type": "user", "emailAddress": "b@example.com"}
                ],
            },
        ]

        _copy_permissions(mock_service, "src_id", "dest_id")

        assert mock_service.permissions().list().execute.call_count == 2
        assert mock_service.permissions().create().execute.call_count == 2

    def test_future_expiration_time_is_preserved(self, mock_service):
        """Test that a still-valid expirationTime is copied onto the new permission."""
        future = (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
        ).isoformat()
        mock_service.permissions().list().execute.return_value = {
            "permissions": [
                {
                    "id": "p1",
                    "role": "reader",
                    "type": "user",
                    "emailAddress": "a@example.com",
                    "expirationTime": future,
                }
            ]
        }

        _copy_permissions(mock_service, "src_id", "dest_id")

        _, kwargs = mock_service.permissions().create.call_args
        assert kwargs["body"]["expirationTime"] == future

    def test_past_expiration_time_is_dropped(self, mock_service):
        """Test that a lapsed expirationTime is not sent (Drive rejects past dates)."""
        past = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        ).isoformat()
        mock_service.permissions().list().execute.return_value = {
            "permissions": [
                {
                    "id": "p1",
                    "role": "reader",
                    "type": "user",
                    "emailAddress": "a@example.com",
                    "expirationTime": past,
                }
            ]
        }

        _copy_permissions(mock_service, "src_id", "dest_id")

        _, kwargs = mock_service.permissions().create.call_args
        assert "expirationTime" not in kwargs["body"]

    def test_send_notification_email_omitted_for_anyone(self, mock_service):
        """Test that sendNotificationEmail is not sent for an 'anyone' grant."""
        mock_service.permissions().list().execute.return_value = {
            "permissions": [{"id": "p1", "role": "reader", "type": "anyone"}]
        }

        _copy_permissions(mock_service, "src_id", "dest_id")

        _, kwargs = mock_service.permissions().create.call_args
        assert "sendNotificationEmail" not in kwargs

    def test_send_notification_email_present_for_user(self, mock_service):
        """Test that sendNotificationEmail=False is still sent for a 'user' grant."""
        mock_service.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "role": "reader", "type": "user", "emailAddress": "a@example.com"}
            ]
        }

        _copy_permissions(mock_service, "src_id", "dest_id")

        _, kwargs = mock_service.permissions().create.call_args
        assert kwargs["sendNotificationEmail"] is False

    def test_permission_list_retries_then_succeeds_on_rate_limit(self, mock_service):
        """Test that a 429 on permissions.list is retried instead of skipped immediately."""
        mock_service.permissions().list().execute.side_effect = [
            _rate_limit_error(),
            {"permissions": []},
        ]

        with patch("time.sleep"):
            _copy_permissions(mock_service, "src_id", "dest_id", max_retries=3, max_backoff=1.0)

        assert mock_service.permissions().list().execute.call_count == 2

    def test_permission_create_retries_then_succeeds_on_rate_limit(self, mock_service):
        """Test that a 429 on permissions.create is retried instead of being dropped."""
        mock_service.permissions().list().execute.return_value = {
            "permissions": [
                {"id": "p1", "role": "reader", "type": "user", "emailAddress": "a@example.com"}
            ]
        }
        mock_service.permissions().create().execute.side_effect = [
            _rate_limit_error(),
            {"id": "new-perm"},
        ]

        with patch("time.sleep"):
            _copy_permissions(mock_service, "src_id", "dest_id", max_retries=3, max_backoff=1.0)

        assert mock_service.permissions().create().execute.call_count == 2

    def test_permission_list_failure_is_logged_and_skipped_after_retries(self, mock_service):
        """Test that an exhausted list retry is caught, logged, and does not raise."""
        mock_service.permissions().list().execute.side_effect = _rate_limit_error()

        with patch("time.sleep"):
            _copy_permissions(mock_service, "src_id", "dest_id", max_retries=2, max_backoff=1.0)

        mock_service.permissions().create.assert_not_called()


# ---------------------------------------------------------------------------
# _list_files_recursive: pagination
# ---------------------------------------------------------------------------
class TestListFilesRecursivePagination:
    """Test that _list_files_recursive follows nextPageToken."""

    def test_processes_every_files_page(self, mock_service):
        """Test that a paginated files.list response is fully consumed."""
        mock_service.files().list().execute.side_effect = [
            {
                "nextPageToken": "page2",
                "files": [{"id": "f1", "name": "a.txt", "mimeType": "text/plain", "size": "10"}],
            },
            {
                "files": [{"id": "f2", "name": "b.txt", "mimeType": "text/plain", "size": "20"}],
            },
        ]

        result = _list_files_recursive("folder_id", mock_service)

        assert {f["name"] for f in result} == {"a.txt", "b.txt"}
        assert mock_service.files().list().execute.call_count == 2


# ---------------------------------------------------------------------------
# _csv_safe: CSV injection escaping
# ---------------------------------------------------------------------------
class TestCsvSafe:
    """Test the CSV-formula-injection guard used by write_duplicate_report."""

    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
    def test_formula_prefixes_are_escaped(self, prefix):
        """Test that a value starting with a formula-trigger character gets a leading apostrophe."""
        value = f"{prefix}cmd|' /C calc'!A1"
        assert _csv_safe(value) == f"'{value}"

    def test_ordinary_value_is_unchanged(self):
        """Test that a normal filename passes through untouched."""
        assert _csv_safe("report.pdf") == "report.pdf"

    def test_empty_value_is_unchanged(self):
        """Test that an empty string doesn't raise (no [0] index error)."""
        assert _csv_safe("") == ""


# ---------------------------------------------------------------------------
# CLI boundary: HttpError during duplicate scan
# ---------------------------------------------------------------------------
class TestDuplicateScanHttpErrorHandling:
    """Test that an HttpError during --duplicate-report exits cleanly."""

    @patch("gcp.copy_folder.authenticate_and_authorize")
    @patch("gcp.copy_folder.create_drive_service")
    @patch("gcp.copy_folder.find_duplicate_files")
    @patch("gcp.copy_folder.write_duplicate_report")
    def test_scan_failure_exits_nonzero_without_writing_report(
        self, mock_write, mock_find, mock_create_service, mock_auth, drive_env
    ):
        """Test that a scan-time HttpError logs, exits 1, and never calls write_duplicate_report."""
        mock_auth.return_value = Mock(valid=True)
        svc = MagicMock()
        mock_create_service.return_value = svc
        svc.files().get().execute.side_effect = [{"name": "Source"}, {"name": "Dest"}]
        mock_find.side_effect = _forbidden_error()

        with drive_env(), pytest.raises(SystemExit) as exc_info:
            main(["--duplicate-report"])

        assert exc_info.value.code == 1
        mock_write.assert_not_called()
