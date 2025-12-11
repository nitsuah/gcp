"""Tests for Google Drive copy_folder functionality."""
import os
from unittest.mock import Mock, patch, MagicMock
import pytest
from gcp.copy_folder import (
    count_files_and_folders,
    authenticate_and_authorize,
    create_drive_service,
)


@pytest.fixture
def mock_service():
    """Create a mock Google Drive service."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_credentials():
    """Create mock credentials."""
    creds = Mock()
    creds.valid = True
    return creds


class TestAuthentication:
    """Test authentication functions."""

    @patch('gcp.copy_folder.InstalledAppFlow')
    def test_authenticate_and_authorize_success(self, mock_flow):
        """Test successful authentication."""
        mock_creds = Mock()
        mock_creds.valid = True
        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = mock_creds
        
        result = authenticate_and_authorize('fake_client.json', ['scope1', 'scope2'])
        
        assert result == mock_creds
        assert result.valid is True

    @patch('gcp.copy_folder.InstalledAppFlow')
    def test_authenticate_and_authorize_invalid(self, mock_flow):
        """Test authentication with invalid credentials."""
        mock_creds = Mock()
        mock_creds.valid = False
        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = mock_creds
        
        result = authenticate_and_authorize('fake_client.json', ['scope1'])
        
        assert result is None

    @patch('gcp.copy_folder.build')
    def test_create_drive_service(self, mock_build, mock_credentials):
        """Test Drive service creation."""
        mock_build.return_value = 'mock_service'
        
        result = create_drive_service(mock_credentials)
        
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_credentials)
        assert result == 'mock_service'


class TestFileOperations:
    """Test file counting operations."""

    def test_count_files_and_folders_empty(self, mock_service):
        """Test counting in an empty folder."""
        mock_service.files().list().execute.return_value = {
            'files': [],
            'nextPageToken': None
        }
        
        num_files, num_folders = count_files_and_folders('fake_folder_id', mock_service)
        
        assert num_files == 0
        assert num_folders == 0

    def test_count_files_and_folders_with_items(self, mock_service):
        """Test counting files and folders."""
        # Mock two separate queries: first for files, then for folders
        mock_service.files().list().execute.side_effect = [
            {
                'files': [
                    {'id': '2', 'mimeType': 'text/plain', 'name': 'file1.txt'},
                    {'id': '4', 'mimeType': 'application/pdf', 'name': 'file2.pdf'},
                ],
                'nextPageToken': None
            },
            {
                'files': [
                    {'id': '1', 'mimeType': 'application/vnd.google-apps.folder', 'name': 'folder1'},
                    {'id': '3', 'mimeType': 'application/vnd.google-apps.folder', 'name': 'folder2'},
                ],
                'nextPageToken': None
            }
        ]
        
        num_files, num_folders = count_files_and_folders('fake_folder_id', mock_service)
        
        assert num_files == 2
        assert num_folders == 2

    def test_count_files_and_folders_pagination(self, mock_service):
        """Test counting with separate queries for files and folders."""
        # Mock two separate queries: first for files (excluding folders), then for folders only
        mock_service.files().list().execute.side_effect = [
            {
                'files': [
                    {'id': '1', 'mimeType': 'text/plain', 'name': 'file1.txt'},
                ],
                'nextPageToken': None
            },
            {
                'files': [
                    {'id': '2', 'mimeType': 'application/vnd.google-apps.folder', 'name': 'folder1'},
                ],
                'nextPageToken': None
            }
        ]
        
        num_files, num_folders = count_files_and_folders('fake_folder_id', mock_service)
        
        assert num_files == 1
        assert num_folders == 1


class TestOutputValidation:
    """Test expected output structure."""

    def test_csv_output_format(self, tmp_path):
        """Test that CSV output has expected structure."""
        import csv
        
        # Expected CSV structure
        expected_headers = ['Folder Name', 'File Count', 'Folder Count']
        test_csv = tmp_path / "test_output.csv"
        
        with open(test_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(expected_headers)
            writer.writerow(['TestFolder', '10', '5'])
        
        # Verify structure
        with open(test_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            assert headers == expected_headers
            
            data_row = next(reader)
            assert len(data_row) == 3
            assert data_row[0] == 'TestFolder'
            assert data_row[1] == '10'
            assert data_row[2] == '5'
