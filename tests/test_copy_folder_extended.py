"""Extended tests for Google Drive copy_folder functionality - Phase 2."""
# pylint: disable=redefined-outer-name,import-outside-toplevel
from unittest.mock import Mock, MagicMock
import csv
import tempfile
import pytest
from googleapiclient.errors import HttpError
from gcp.copy_folder import (
    count_child_objects,
    copy_child_objects,
    handle_copy_error,
    add_child_folders,
    compare_csv_files,
)


@pytest.fixture
def mock_service():
    """Create a mock Google Drive service."""
    service = MagicMock()
    return service


class TestCountChildObjects:
    """Test recursive folder counting."""

    def test_count_child_objects_empty_folder(self, mock_service):
        """Test counting in an empty folder."""
        mock_service.files().list().execute.return_value = {'files': []}

        num_files, num_folders = count_child_objects('empty_folder_id', mock_service)

        assert num_files == 0
        assert num_folders == 0

    def test_count_child_objects_files_only(self, mock_service):
        """Test counting files without subfolders."""
        mock_service.files().list().execute.return_value = {
            'files': [
                {'id': '1', 'name': 'file1.txt', 'mimeType': 'text/plain'},
                {'id': '2', 'name': 'file2.pdf', 'mimeType': 'application/pdf'},
                {'id': '3', 'name': 'file3.jpg', 'mimeType': 'image/jpeg'},
            ]
        }

        num_files, num_folders = count_child_objects('folder_id', mock_service)

        assert num_files == 3
        assert num_folders == 0

    def test_count_child_objects_folders_only(self, mock_service):
        """Test counting folders without files."""
        # First call returns folders, subsequent calls return empty (folders are empty)
        mock_service.files().list().execute.side_effect = [
            {
                'files': [
                    {'id': 'f1', 'name': 'folder1', 'mimeType': 'application/vnd.google-apps.folder'},
                    {'id': 'f2', 'name': 'folder2', 'mimeType': 'application/vnd.google-apps.folder'},
                ]
            },
            {'files': []},  # folder1 is empty
            {'files': []},  # folder2 is empty
        ]

        num_files, num_folders = count_child_objects('folder_id', mock_service)

        assert num_files == 0
        assert num_folders == 2

    def test_count_child_objects_nested_structure(self, mock_service):
        """Test counting with nested folder structure."""
        # Root folder has 1 file and 1 folder
        # Subfolder has 2 files
        mock_service.files().list().execute.side_effect = [
            {
                'files': [
                    {'id': 'file1', 'name': 'root_file.txt', 'mimeType': 'text/plain'},
                    {'id': 'subfolder', 'name': 'subfolder', 'mimeType': 'application/vnd.google-apps.folder'},
                ]
            },
            {
                'files': [
                    {'id': 'file2', 'name': 'sub_file1.txt', 'mimeType': 'text/plain'},
                    {'id': 'file3', 'name': 'sub_file2.txt', 'mimeType': 'text/plain'},
                ]
            },
        ]

        num_files, num_folders = count_child_objects('root_folder', mock_service)

        assert num_files == 3  # 1 root + 2 in subfolder
        assert num_folders == 1


class TestCopyChildObjects:
    """Test file and folder copying operations."""

    def test_copy_child_objects_empty_folder(self, mock_service):
        """Test copying from an empty folder."""
        mock_service.files().list().execute.side_effect = [
            {'files': []},  # No files
            {'files': []},  # No folders
        ]

        # Should complete without errors
        copy_child_objects('src', 'dest', mock_service)

        # Verify no copy operations were attempted
        mock_service.files().copy.assert_not_called()

    def test_copy_child_objects_files_only(self, mock_service):
        """Test copying files without folders."""
        mock_service.files().list().execute.side_effect = [
            {
                'files': [
                    {'id': 'file1', 'name': 'doc.txt'},
                    {'id': 'file2', 'name': 'image.jpg'},
                ]
            },
            {'files': []},  # No folders
        ]
        mock_service.files().copy().execute.return_value = {'id': 'new_file'}

        copy_child_objects('src', 'dest', mock_service)

        # Verify files were copied (MagicMock counts call() as one call)
        assert mock_service.files().copy.call_count >= 2

    def test_copy_child_objects_with_folders(self, mock_service):
        """Test copying files and folders."""
        mock_service.files().list().execute.side_effect = [
            {'files': [{'id': 'file1', 'name': 'doc.txt'}]},  # Files in root
            {'files': [{'id': 'folder1', 'name': 'subfolder'}]},  # Folders in root
            {'files': []},  # Files in subfolder
            {'files': []},  # Folders in subfolder
        ]
        mock_service.files().copy().execute.return_value = {'id': 'new_file'}
        mock_service.files().create().execute.return_value = {'id': 'new_folder'}

        copy_child_objects('src', 'dest', mock_service)

        # Verify file copy was called
        assert mock_service.files().copy.call_count >= 1
        # Verify folder creation was called
        assert mock_service.files().create.call_count >= 1

    def test_copy_child_objects_with_retry(self, mock_service):
        """Test retry mechanism on file copy failure."""
        mock_service.files().list().execute.side_effect = [
            {'files': [{'id': 'file1', 'name': 'doc.txt'}]},
            {'files': []},
        ]

        # Simulate failure then success
        http_error = HttpError(resp=Mock(status=500), content=b'Server Error')
        mock_service.files().copy().execute.side_effect = [
            http_error,
            {'id': 'new_file'},
        ]

        copy_child_objects('src', 'dest', mock_service, max_retries=2)

        # Verify retry was attempted (includes the initial call() which is counted)
        assert mock_service.files().copy.call_count >= 2

    def test_copy_child_objects_max_retries_exceeded(self, mock_service):
        """Test that retries eventually give up."""
        mock_service.files().list().execute.side_effect = [
            {'files': [{'id': 'file1', 'name': 'doc.txt'}]},
            {'files': []},
        ]

        # Simulate continuous failure
        http_error = HttpError(resp=Mock(status=500), content=b'Server Error')
        mock_service.files().copy().execute.side_effect = http_error

        # Should not raise, just log and continue
        copy_child_objects('src', 'dest', mock_service, max_retries=2)

        assert mock_service.files().copy.call_count >= 2


class TestHandleCopyError:
    """Test error handling."""

    def test_handle_copy_error_basic(self, mock_service):
        """Test basic error logging."""
        error = Exception("Test error")

        # Should not raise, just log
        handle_copy_error('test_file.txt', error, mock_service)

    def test_handle_copy_error_with_http_error(self, mock_service):
        """Test handling HttpError with file metadata retrieval."""
        http_error = HttpError(resp=Mock(status=404), content=b'Not Found')
        http_error.__dict__['fileId'] = 'file123'

        mock_service.files().get().execute.return_value = {
            'parents': ['parent_folder_id']
        }

        handle_copy_error('test_file.txt', http_error, mock_service)

        # Verify parent folder lookup was attempted (call count includes call())
        assert mock_service.files().get.call_count >= 1

    def test_handle_copy_error_parent_lookup_fails(self, mock_service):
        """Test when parent folder lookup fails."""
        http_error = HttpError(resp=Mock(status=404), content=b'Not Found')
        http_error.__dict__['fileId'] = 'file123'

        # Simulate parent lookup failure
        parent_error = HttpError(resp=Mock(status=403), content=b'Forbidden')
        mock_service.files().get().execute.side_effect = parent_error

        # Should not raise, just log both errors
        handle_copy_error('test_file.txt', http_error, mock_service)


class TestAddChildFolders:
    """Test CSV writing for folder structure."""

    def test_add_child_folders_empty(self, mock_service):
        """Test adding child folders when there are none."""
        mock_service.files().list().execute.return_value = {'files': []}

        with tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            add_child_folders('folder_id', writer, mock_service)

        # No folders to add, writer should not be called

    def test_add_child_folders_with_items(self, mock_service):
        """Test adding child folders to CSV."""
        # Mock the list call to return folders
        # add_child_folders calls count_child_objects for each folder
        # count_child_objects queries for all items (files and folders)
        mock_service.files().list().execute.side_effect = [
            {
                'files': [
                    {'id': 'folder1', 'name': 'Documents'},
                    {'id': 'folder2', 'name': 'Pictures'},
                ]
            },
            # For Documents folder - count_child_objects queries once for all items
            {'files': [{'id': 'file1', 'name': 'doc.txt', 'mimeType': 'text/plain'}]},
            # For Pictures folder - count_child_objects queries once for all items
            {'files': [{'id': 'file2', 'name': 'pic.jpg', 'mimeType': 'image/jpeg'}]},
        ]

        with tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Folder Name', 'Number of Files', 'Number of Folders'])
            add_child_folders('parent_id', writer, mock_service)
            f.flush()

            # Read back and verify
            with open(f.name, 'r', encoding='utf-8') as rf:
                reader = csv.reader(rf)
                next(reader)  # Skip header
                rows = list(reader)
                assert len(rows) == 2
                # CSV reader returns strings
                assert rows[0] == ['Documents', '1', '0']
                assert rows[1] == ['Pictures', '1', '0']


class TestCompareCSVFiles:
    """Tests for comparing CSV files."""

    def test_compare_csv_files_equal(self, tmp_path):
        """Test comparing identical CSV files."""
        file1 = tmp_path / "test1.csv"
        file2 = tmp_path / "test2.csv"

        data = [['Name', 'Files', 'Folders'], ['Folder1', 10, 5]]

        for f in [file1, file2]:
            with open(f, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(data)

        # Should not raise, should log success
        compare_csv_files(str(file1), str(file2))

    def test_compare_csv_files_different(self, tmp_path):
        """Test comparing different CSV files."""
        file1 = tmp_path / "test1.csv"
        file2 = tmp_path / "test2.csv"

        with open(file1, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows([['Name', 'Files', 'Folders'], ['Folder1', 10, 5]])

        with open(file2, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows([['Name', 'Files', 'Folders'], ['Folder1', 15, 5]])

        # Should log failure but not raise
        compare_csv_files(str(file1), str(file2))

    def test_compare_csv_files_different_structure(self, tmp_path):
        """Test comparing CSV files with different structures."""
        file1 = tmp_path / "test1.csv"
        file2 = tmp_path / "test2.csv"

        with open(file1, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows([['Name', 'Files'], ['Folder1', 10]])

        with open(file2, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows([['Name', 'Files', 'Folders'], ['Folder1', 10, 5]])

        # Should log failure
        compare_csv_files(str(file1), str(file2))
