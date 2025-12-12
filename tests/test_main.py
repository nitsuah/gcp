"""
Tests for the main entry point and CLI functionality of copy_folder.
"""
import os
from unittest.mock import patch, mock_open, MagicMock
import pytest
from googleapiclient.errors import HttpError
from gcp.copy_folder import main


class TestMainFunction:
    """Test the main() CLI function"""

    @patch('gcp.copy_folder.authenticate_and_authorize')
    @patch('gcp.copy_folder.create_drive_service')
    @patch('gcp.copy_folder.count_child_objects')
    @patch('gcp.copy_folder.add_child_folders')
    @patch('gcp.copy_folder.copy_child_objects')
    @patch('gcp.copy_folder.compare_csv_files')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.environ.get')
    def test_main_successful_execution(
        self,
        mock_env,
        mock_file_open,
        mock_compare,
        mock_copy,
        mock_add_child,
        mock_count,
        mock_create_service,
        mock_auth
    ):
        """Test main function with successful execution"""
        # Setup environment variables
        mock_env.side_effect = lambda key: {
            'GOOGLE_DRIVE_CLIENT_ID_FILE': 'client_id.json',
            'GOOGLE_DRIVE_SOURCE_FOLDER_ID': 'source123',
            'GOOGLE_DRIVE_DESTINATION_FOLDER_ID': 'dest456'
        }.get(key)

        # Setup mocks
        mock_creds = MagicMock()
        mock_auth.return_value = mock_creds

        mock_service = MagicMock()
        mock_create_service.return_value = mock_service

        # Mock get() calls for folder names
        mock_service.files().get().execute.side_effect = [
            {'name': 'Source Folder'},
            {'name': 'Destination Folder'}
        ]

        # Mock count_child_objects to return file and folder counts
        mock_count.return_value = (10, 5)

        # Execute main
        main()

        # Verify authentication was called
        mock_auth.assert_called_once_with('client_id.json', [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.metadata.readonly'
        ])

        # Verify service was created
        mock_create_service.assert_called_once_with(mock_creds)

        # Verify count was called for source and destination
        assert mock_count.call_count == 3  # Once for assessment-1, once each for assessment-2 & 3

        # Verify copy was called
        mock_copy.assert_called_once_with('source123', 'dest456', mock_service)

        # Verify comparison was called
        mock_compare.assert_called_once_with('./outputs/assessment-2.csv', './outputs/assessment-3.csv')

    @patch('os.environ.get')
    def test_main_missing_client_id(self, mock_env):
        """Test main function raises error when CLIENT_ID is missing"""
        mock_env.side_effect = lambda key: {
            'GOOGLE_DRIVE_SOURCE_FOLDER_ID': 'source123',
            'GOOGLE_DRIVE_DESTINATION_FOLDER_ID': 'dest456'
        }.get(key)

        with pytest.raises(ValueError, match="Missing environment variable.*Client ID"):
            main()

    @patch('os.environ.get')
    def test_main_missing_source_folder_id(self, mock_env):
        """Test main function raises error when SOURCE_FOLDER_ID is missing"""
        mock_env.side_effect = lambda key: {
            'GOOGLE_DRIVE_CLIENT_ID_FILE': 'client_id.json',
            'GOOGLE_DRIVE_DESTINATION_FOLDER_ID': 'dest456'
        }.get(key)

        with pytest.raises(ValueError, match="Missing environment variable.*Source folder"):
            main()

    @patch('os.environ.get')
    def test_main_missing_destination_folder_id(self, mock_env):
        """Test main function raises error when DESTINATION_FOLDER_ID is missing"""
        mock_env.side_effect = lambda key: {
            'GOOGLE_DRIVE_CLIENT_ID_FILE': 'client_id.json',
            'GOOGLE_DRIVE_SOURCE_FOLDER_ID': 'source123'
        }.get(key)

        with pytest.raises(ValueError, match="Missing environment variable.*Destination folder"):
            main()

    @patch('gcp.copy_folder.authenticate_and_authorize')
    @patch('os.environ.get')
    def test_main_authentication_failure(self, mock_env, mock_auth):
        """Test main function raises RuntimeError when authentication fails"""
        mock_env.side_effect = lambda key: {
            'GOOGLE_DRIVE_CLIENT_ID_FILE': 'client_id.json',
            'GOOGLE_DRIVE_SOURCE_FOLDER_ID': 'source123',
            'GOOGLE_DRIVE_DESTINATION_FOLDER_ID': 'dest456'
        }.get(key)

        # Return None to simulate auth failure
        mock_auth.return_value = None

        with pytest.raises(RuntimeError, match="Failed to authenticate"):
            main()

    @patch('gcp.copy_folder.authenticate_and_authorize')
    @patch('gcp.copy_folder.create_drive_service')
    @patch('gcp.copy_folder.count_child_objects')
    @patch('gcp.copy_folder.add_child_folders')
    @patch('gcp.copy_folder.copy_child_objects')
    @patch('gcp.copy_folder.compare_csv_files')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.environ.get')
    def test_main_csv_file_creation(
        self,
        mock_env,
        mock_file_open,
        mock_compare,
        mock_copy,
        mock_add_child,
        mock_count,
        mock_create_service,
        mock_auth
    ):
        """Test that main creates all CSV output files correctly"""
        mock_env.side_effect = lambda key: {
            'GOOGLE_DRIVE_CLIENT_ID_FILE': 'client_id.json',
            'GOOGLE_DRIVE_SOURCE_FOLDER_ID': 'source123',
            'GOOGLE_DRIVE_DESTINATION_FOLDER_ID': 'dest456'
        }.get(key)

        mock_creds = MagicMock()
        mock_auth.return_value = mock_creds
        mock_service = MagicMock()
        mock_create_service.return_value = mock_service

        mock_service.files().get().execute.side_effect = [
            {'name': 'Source'},
            {'name': 'Dest'}
        ]

        mock_count.return_value = (100, 20)

        main()

        # Verify all CSV files were opened for writing
        expected_files = [
            './outputs/assessment-1.csv',
            './outputs/assessment-2.csv',
            './outputs/assessment-3.csv'
        ]

        open_calls = [call[0][0] for call in mock_file_open.call_args_list]
        for expected_file in expected_files:
            assert expected_file in open_calls, f"Expected {expected_file} to be opened"

    @patch('gcp.copy_folder.authenticate_and_authorize')
    @patch('gcp.copy_folder.create_drive_service')
    @patch('gcp.copy_folder.count_child_objects')
    @patch('gcp.copy_folder.add_child_folders')
    @patch('gcp.copy_folder.copy_child_objects')
    @patch('gcp.copy_folder.compare_csv_files')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.environ.get')
    def test_main_folder_name_retrieval(
        self,
        mock_env,
        mock_file_open,
        mock_compare,
        mock_copy,
        mock_add_child,
        mock_count,
        mock_create_service,
        mock_auth
    ):
        """Test that main retrieves folder names correctly"""
        mock_env.side_effect = lambda key: {
            'GOOGLE_DRIVE_CLIENT_ID_FILE': 'client_id.json',
            'GOOGLE_DRIVE_SOURCE_FOLDER_ID': 'source123',
            'GOOGLE_DRIVE_DESTINATION_FOLDER_ID': 'dest456'
        }.get(key)

        mock_creds = MagicMock()
        mock_auth.return_value = mock_creds
        mock_service = MagicMock()
        mock_create_service.return_value = mock_service

        # Setup get() calls
        mock_get = mock_service.files().get
        mock_get().execute.side_effect = [
            {'name': 'My Source Folder'},
            {'name': 'My Destination Folder'}
        ]

        mock_count.return_value = (5, 3)

        main()

        # Verify get was called with correct parameters for folder names
        assert mock_get.call_count >= 2
        mock_get.assert_any_call(fileId='source123', fields='name')
        mock_get.assert_any_call(fileId='dest456', fields='name')


class TestMainIntegration:
    """Additional integration tests for main()"""

    @patch('gcp.copy_folder.authenticate_and_authorize')
    @patch('gcp.copy_folder.create_drive_service')
    @patch('gcp.copy_folder.count_child_objects')
    @patch('gcp.copy_folder.add_child_folders')
    @patch('gcp.copy_folder.copy_child_objects')
    @patch('gcp.copy_folder.compare_csv_files')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.environ.get')
    def test_main_complete_workflow(
        self,
        mock_env,
        mock_file_open,
        mock_compare,
        mock_copy,
        mock_add_child,
        mock_count,
        mock_create_service,
        mock_auth
    ):
        """Test that main executes all steps in correct order"""
        mock_env.side_effect = lambda key: {
            'GOOGLE_DRIVE_CLIENT_ID_FILE': 'creds.json',
            'GOOGLE_DRIVE_SOURCE_FOLDER_ID': 'src',
            'GOOGLE_DRIVE_DESTINATION_FOLDER_ID': 'dst'
        }.get(key)

        mock_auth.return_value = MagicMock()
        mock_service = MagicMock()
        mock_create_service.return_value = mock_service
        mock_service.files().get().execute.side_effect = [
            {'name': 'Source'},
            {'name': 'Dest'}
        ]
        mock_count.return_value = (50, 10)

        main()

        # Verify workflow steps
        assert mock_auth.called
        assert mock_create_service.called
        assert mock_count.call_count == 3  # Once for assessment-1, once each for 2 & 3
        assert mock_add_child.call_count == 2  # assessment-2 and assessment-3
        assert mock_copy.call_count == 1
        assert mock_compare.call_count == 1

    @patch('gcp.copy_folder.authenticate_and_authorize')
    @patch('gcp.copy_folder.create_drive_service')
    @patch('gcp.copy_folder.count_child_objects')
    @patch('gcp.copy_folder.add_child_folders')
    @patch('gcp.copy_folder.copy_child_objects')
    @patch('gcp.copy_folder.compare_csv_files')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.environ.get')
    def test_main_assessment_file_writes(
        self,
        mock_env,
        mock_file_open,
        mock_compare,
        mock_copy,
        mock_add_child,
        mock_count,
        mock_create_service,
        mock_auth
    ):
        """Test that assessment CSV files are written correctly"""
        mock_env.side_effect = lambda key: {
            'GOOGLE_DRIVE_CLIENT_ID_FILE': 'test.json',
            'GOOGLE_DRIVE_SOURCE_FOLDER_ID': 'abc',
            'GOOGLE_DRIVE_DESTINATION_FOLDER_ID': 'xyz'
        }.get(key)

        mock_auth.return_value = MagicMock()
        mock_service = MagicMock()
        mock_create_service.return_value = mock_service
        mock_service.files().get().execute.side_effect = [
            {'name': 'TestSource'},
            {'name': 'TestDest'}
        ]
        mock_count.return_value = (25, 8)

        main()

        # Check that all three assessment files were created
        calls = [str(call) for call in mock_file_open.call_args_list]
        assert any('assessment-1.csv' in call for call in calls)
        assert any('assessment-2.csv' in call for call in calls)
        assert any('assessment-3.csv' in call for call in calls)
