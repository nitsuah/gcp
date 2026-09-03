"""
A script using the Google Drive API to create reports and copy contents between folders.
"""

import argparse
import csv
import datetime
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError  # pylint: disable=ungrouped-imports

# Define API scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

# Environment variables
CLIENT_ID_ENV_VAR = "GOOGLE_DRIVE_CLIENT_ID_FILE"
SOURCE_FOLDER_ID_ENV_VAR = "GOOGLE_DRIVE_SOURCE_FOLDER_ID"
DESTINATION_FOLDER_ID_ENV_VAR = "GOOGLE_DRIVE_DESTINATION_FOLDER_ID"

# Script Constants
MISSING_ENVAR_TXT = "Missing environment variable for"
MIME_FOLDER = "application/vnd.google-apps.folder"
DEFAULT_PROGRESS_LOG_EVERY = 25
DEFAULT_MAX_BACKOFF = 60.0
DEFAULT_WORKERS = 1

# Convenience aliases for --include-mime / --exclude-mime CLI args
MIME_ALIASES = {
    "docs": "application/vnd.google-apps.document",
    "sheets": "application/vnd.google-apps.spreadsheet",
    "slides": "application/vnd.google-apps.presentation",
    "forms": "application/vnd.google-apps.form",
    "drawings": "application/vnd.google-apps.drawing",
    "pdf": "application/pdf",
    "images": "image/",
    "text": "text/",
    "video": "video/",
    "audio": "audio/",
    "zip": "application/zip",
}

# Directories and filenames
OUTPUTS_DIRECTORY = "./outputs/"
DUPLICATE_REPORT_PATH = "./outputs/duplicate-report.csv"

# Permission roles that are never mirrored: ownership cannot be transferred by
# granting a permission (Drive requires a separate ownership-transfer flow), so
# mirroring an "owner" role onto the destination file/folder would just fail.
NON_MIRRORABLE_ROLES = {"owner"}

# Log format used when initializing the file handler in main()
LOG_FILE_FORMAT = (
    "%(asctime)s %(levelname)s %(message)s %(filename)s %(funcName)s %(lineno)d"
)

# RCA: logging.basicConfig(filename=...) was previously called at module level, which
# attempted to open ./outputs/<log>.log immediately on import.  When the outputs/
# directory did not exist (e.g. in a fresh CI checkout or test run from a different
# working directory) Python raised FileNotFoundError and the entire module failed to
# import, breaking every test that tried to 'from gcp.copy_folder import ...'.
# Fix: use a stream-based logger at module scope; configure the file handler inside
# main() only after ensuring the outputs directory exists.
logging.basicConfig(level=logging.INFO, format=LOG_FILE_FORMAT)

# Module-level variables will be initialized in main()
# This prevents execution on import
service = None  # pylint: disable=invalid-name


def _resolve_mime_aliases(mime_list):
    """Expand short alias tokens (e.g. 'docs', 'pdf') to full MIME type strings."""
    return [MIME_ALIASES.get(token.lower(), token) for token in mime_list]


def _mime_matches(mime_type, patterns):
    """Return True if mime_type matches any pattern (prefix match for patterns ending with /)."""
    for pattern in patterns:
        if pattern.endswith("/"):
            if mime_type.startswith(pattern):
                return True
        elif mime_type == pattern:
            return True
    return False


def _file_passes_filter(file_mime_type, include_mime, exclude_mime):
    """
    Return True if a file should be processed given the MIME filters.
    exclude_mime takes priority; include_mime acts as an allowlist when non-empty.
    """
    if exclude_mime and _mime_matches(file_mime_type, exclude_mime):
        return False
    if include_mime and not _mime_matches(file_mime_type, include_mime):
        return False
    return True


# Create a flow to handle the OAuth2 authentication
def authenticate_and_authorize(client_id_file, api_scopes):
    """
    Handles OAuth2 authentication and authorization.

    Args:
        client_id_file (str): The path to the client ID JSON file.
        api_scopes (list): The list of API scopes.

    Returns:
        credentials (google.oauth2.credentials.Credentials): The authorized credentials.
    """
    flow = InstalledAppFlow.from_client_secrets_file(client_id_file, api_scopes)
    auth_credentials = flow.run_local_server()

    if auth_credentials and auth_credentials.valid:
        return auth_credentials
    return None


def create_drive_service(valid_credentials):
    """
    Creates a Google Drive API service object.

    Args:
        valid_credentials (google.oauth2.credentials.Credentials): The authorized credentials.

    Returns:
        service (googleapiclient.discovery.Resource): The Drive API service object.
    """
    return build("drive", "v3", credentials=valid_credentials)


# MAGIC Constants - to improve readability & linting
# Disable pylint for no-member at the function level
# pylint: disable=no-member


# Define a function to count files and folders
def count_files_and_folders(folder_id, drive_service=None):
    """
    Counts the number of FILES and FOLDERS in a given folder_id.

    Args:
        folder_id (str): The ID of the folder to count files and folders in.
        drive_service: The Google Drive service object (optional, uses global if not provided).

    Returns:
        num_files (int): The total number of files in the folder.
        num_folders (int): The total number of folders in the folder.
    """
    svc = drive_service or service
    # Count Files
    query = (
        f"'{folder_id}' in parents and mimeType != '{MIME_FOLDER}' "
        f"and trashed = false"
    )
    results = svc.files().list(q=query).execute()
    files = results.get("files", [])
    num_files = len(files)
    # Count Folders
    query = (
        f"'{folder_id}' in parents and mimeType = '{MIME_FOLDER}' "
        f"and trashed = false"
    )
    results = svc.files().list(q=query).execute()
    folders = results.get("files", [])
    num_folders = len(folders)

    return num_files, num_folders


# Define a function to count child objects recursively
def count_child_objects(
    folder_id, drive_service=None, *, include_mime=None, exclude_mime=None
):
    """
    Recursively counts the number of files and folders in a given folder and its subfolders.

    Args:
        folder_id (str): The ID of the folder to count files and folders for.
        drive_service: The Google Drive service object (optional, uses global if not provided).
        include_mime (list): If set, only count files whose MIME type matches a pattern.
        exclude_mime (list): If set, skip files whose MIME type matches a pattern.

    Returns:
        num_files (int): The total number of files in the folder and its subfolders.
        num_folders (int): The total number of folders in the folder and its subfolders.
    """
    svc = drive_service or service
    inc = include_mime or []
    exc = exclude_mime or []
    query = f"'{folder_id}' in parents and trashed = false"
    results = svc.files().list(q=query).execute()
    files_and_folders = results.get("files", [])
    num_files = 0
    num_folders = 0

    for item in files_and_folders:
        if item["mimeType"] == MIME_FOLDER:
            child_num_files, child_num_folders = count_child_objects(
                item["id"], svc, include_mime=include_mime, exclude_mime=exclude_mime
            )
            num_files += child_num_files
            num_folders += child_num_folders + 1
        else:
            if _file_passes_filter(item["mimeType"], inc, exc):
                num_files += 1

    return num_files, num_folders


def _dest_has_file(svc, dest_folder_id, filename):
    """Return True if a non-trashed file with filename exists in dest_folder_id."""
    safe_name = filename.replace("'", "\\'")
    query = (
        f"'{dest_folder_id}' in parents and name = '{safe_name}' "
        f"and mimeType != '{MIME_FOLDER}' and trashed = false"
    )
    results = svc.files().list(q=query, fields="files(id)", pageSize=1).execute()
    return bool(results.get("files"))


def _dest_has_folder(svc, dest_folder_id, folder_name):
    """Return the ID of an existing non-trashed subfolder named folder_name, or None."""
    safe_name = folder_name.replace("'", "\\'")
    query = (
        f"'{dest_folder_id}' in parents and name = '{safe_name}' "
        f"and mimeType = '{MIME_FOLDER}' and trashed = false"
    )
    results = svc.files().list(q=query, fields="files(id)", pageSize=1).execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def _copy_permissions(svc, src_id, dest_id):
    """
    Copy sharing/ACL permissions from src_id (file or folder) onto dest_id.

    Ownership ("owner" role) is never mirrored -- Drive requires a separate
    ownership-transfer flow, and the destination owner is whoever authenticated
    the copy. Individual permission failures (e.g. a domain permission that
    does not exist in the destination's organization) are logged and skipped
    rather than aborting the whole copy.
    """
    try:
        results = (
            svc.permissions()
            .list(
                fileId=src_id,
                fields="permissions(id,role,type,emailAddress,domain,allowFileDiscovery)",
            )
            .execute()
        )
    except HttpError as err:
        logging.error("Failed to list permissions for %s: %s", src_id, err)
        return

    for perm in results.get("permissions", []):
        role = perm.get("role")
        perm_type = perm.get("type")
        if role in NON_MIRRORABLE_ROLES:
            continue

        body = {"role": role, "type": perm_type}
        if perm_type in ("user", "group") and perm.get("emailAddress"):
            body["emailAddress"] = perm["emailAddress"]
        elif perm_type == "domain" and perm.get("domain"):
            body["domain"] = perm["domain"]
        elif perm_type == "anyone":
            if "allowFileDiscovery" in perm:
                body["allowFileDiscovery"] = perm["allowFileDiscovery"]
        else:
            # Missing the identifying field this permission type requires
            # (e.g. a "user" entry with no emailAddress) -- skip rather than
            # send a request Drive will reject.
            continue

        try:
            svc.permissions().create(
                fileId=dest_id,
                body=body,
                sendNotificationEmail=False,
                fields="id",
            ).execute()
        except HttpError as err:
            logging.error(
                "Failed to mirror permission (role=%s type=%s) onto %s: %s",
                role,
                perm_type,
                dest_id,
                err,
            )


def _copy_file_with_backoff(
    svc, file, dest_folder_id, max_retries, max_backoff, mirror_permissions=False
):
    """
    Copy a single file with exponential backoff for transient and rate-limit errors.

    When mirror_permissions is True, sharing/ACL permissions are copied from the
    source file onto the newly created destination file after a successful copy.

    Returns True on success, False if all retries are exhausted.
    """
    file_metadata = {"name": file["name"], "parents": [dest_folder_id]}
    delay = 1.0
    for attempt in range(max_retries):
        try:
            new_file = (
                svc.files()
                .copy(fileId=file["id"], body=file_metadata, fields="id")
                .execute()
            )
            if mirror_permissions:
                _copy_permissions(svc, file["id"], new_file["id"])
            return True
        except HttpError as err:
            is_rate_limit = err.resp.status in (429, 503)
            if attempt < max_retries - 1:
                sleep_time = min(delay + random.uniform(0, 1), max_backoff)
                log_level = logging.WARNING if is_rate_limit else logging.ERROR
                logging.log(
                    log_level,
                    "Error copying %s (attempt %d/%d, retry in %.1fs): %s",
                    file["name"],
                    attempt + 1,
                    max_retries,
                    sleep_time,
                    err,
                )
                time.sleep(sleep_time)
                delay = min(delay * 2, max_backoff)
            else:
                logging.error(
                    "Error copying file %s after %d retries: %s",
                    file["name"],
                    max_retries,
                    err,
                )
    return False


def _create_progress_tracker(progress_log_every):
    return {
        "start_time": time.monotonic(),
        "copied_files": 0,
        "created_folders": 0,
        "failed_files": 0,
        "skipped_files": 0,
        "processed_since_log": 0,
        "progress_log_every": max(1, int(progress_log_every)),
    }


def _log_progress_if_needed(progress_tracker, force=False):
    if (
        not force
        and progress_tracker["processed_since_log"]
        < progress_tracker["progress_log_every"]
    ):
        return

    elapsed = time.monotonic() - progress_tracker["start_time"]
    logging.info(
        "COPY PROGRESS: files=%d folders=%d failed=%d skipped=%d elapsed=%.2fs",
        progress_tracker["copied_files"],
        progress_tracker["created_folders"],
        progress_tracker["failed_files"],
        progress_tracker["skipped_files"],
        elapsed,
    )
    progress_tracker["processed_since_log"] = 0


def _log_progress_summary(progress_tracker):
    elapsed = time.monotonic() - progress_tracker["start_time"]
    logging.info(
        "COPY PROGRESS SUMMARY: files=%d folders=%d failed=%d skipped=%d total_elapsed=%.2fs",
        progress_tracker["copied_files"],
        progress_tracker["created_folders"],
        progress_tracker["failed_files"],
        progress_tracker["skipped_files"],
        elapsed,
    )


# Define a function to copy child objects recursively
def copy_child_objects(
    src_folder_id,
    dest_folder_id,
    drive_service=None,
    *,
    max_retries=1,
    max_backoff=DEFAULT_MAX_BACKOFF,
    workers=DEFAULT_WORKERS,
    include_mime=None,
    exclude_mime=None,
    skip_existing=False,
    mirror_permissions=False,
    progress_tracker=None,
    progress_log_every=DEFAULT_PROGRESS_LOG_EVERY,
):
    """
    Copies all child objects (files and folders) from source folder to a destination folder.

    Args:
        src_folder_id (str): The id for the source folder.
        dest_folder_id (str): The id for the destination folder.
        drive_service: The Google Drive service object (optional, uses global if not provided).
        max_retries (int): Maximum retry attempts per file (with exponential backoff).
        max_backoff (float): Maximum backoff delay in seconds between retries.
        workers (int): Number of parallel copy workers (1 = sequential).
        include_mime (list): If set, only copy files whose MIME type matches a pattern.
        exclude_mime (list): If set, skip files whose MIME type matches a pattern.
        skip_existing (bool): If True, skip files/folders already present in destination.
        mirror_permissions (bool): If True, copy sharing/ACL permissions from each source
            file/folder onto its newly created destination counterpart (applies only to
            objects copied/created during this run, not ones reused via skip_existing).
    """
    svc = drive_service or service
    root_call = progress_tracker is None
    tracker = progress_tracker or _create_progress_tracker(progress_log_every)
    inc = include_mime or []
    exc = exclude_mime or []

    # List all items in the source folder (files + subfolders handled separately below)
    query = f"'{src_folder_id}' in parents"
    results = svc.files().list(q=query).execute()
    all_items = results.get("files", [])

    # Partition into files-to-copy and skipped
    files_to_copy = []
    for item in all_items:
        mime = item.get("mimeType", "")
        if mime == MIME_FOLDER:
            continue  # folders are handled in the second pass
        if skip_existing and _dest_has_file(svc, dest_folder_id, item["name"]):
            logging.debug("Skipping existing file: %s", item["name"])
            tracker["skipped_files"] += 1
            tracker["processed_since_log"] += 1
            _log_progress_if_needed(tracker)
            continue
        if _file_passes_filter(mime, inc, exc):
            files_to_copy.append(item)
        else:
            tracker["skipped_files"] += 1
            tracker["processed_since_log"] += 1
            _log_progress_if_needed(tracker)

    def _copy_one(file):
        success = _copy_file_with_backoff(
            svc, file, dest_folder_id, max_retries, max_backoff, mirror_permissions
        )
        return file, success

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_copy_one, f): f for f in files_to_copy}
            for future in as_completed(futures):
                file, success = future.result()
                if success:
                    tracker["copied_files"] += 1
                else:
                    tracker["failed_files"] += 1
                    handle_copy_error(
                        file["name"], RuntimeError("Max retries exceeded"), svc
                    )
                tracker["processed_since_log"] += 1
                _log_progress_if_needed(tracker)
    else:
        for file in files_to_copy:
            success = _copy_file_with_backoff(
                svc, file, dest_folder_id, max_retries, max_backoff, mirror_permissions
            )
            if success:
                tracker["copied_files"] += 1
            else:
                tracker["failed_files"] += 1
                handle_copy_error(
                    file["name"], RuntimeError("Max retries exceeded"), svc
                )
            tracker["processed_since_log"] += 1
            _log_progress_if_needed(tracker)

    # List folders in the source folder and recurse
    query = f"'{src_folder_id}' in parents and mimeType = '{MIME_FOLDER}'"
    results = svc.files().list(q=query).execute()
    folders = results.get("files", [])

    for folder in folders:
        existing_folder_id = _dest_has_folder(svc, dest_folder_id, folder["name"]) if skip_existing else None
        if existing_folder_id:
            logging.debug("Reusing existing folder: %s", folder["name"])
            child_dest_id = existing_folder_id
        else:
            new_folder_metadata = {
                "name": folder["name"],
                "parents": [dest_folder_id],
                "mimeType": MIME_FOLDER,
            }
            new_folder = svc.files().create(body=new_folder_metadata, fields="id").execute()
            child_dest_id = new_folder["id"]
            tracker["created_folders"] += 1
            if mirror_permissions:
                _copy_permissions(svc, folder["id"], child_dest_id)
        tracker["processed_since_log"] += 1
        _log_progress_if_needed(tracker)
        copy_child_objects(
            folder["id"],
            child_dest_id,
            svc,
            max_retries=max_retries,
            max_backoff=max_backoff,
            workers=workers,
            include_mime=include_mime,
            exclude_mime=exclude_mime,
            skip_existing=skip_existing,
            mirror_permissions=mirror_permissions,
            progress_tracker=tracker,
            progress_log_every=progress_log_every,
        )

    if root_call:
        _log_progress_if_needed(tracker, force=True)
        _log_progress_summary(tracker)


# Define a function to handle copy errors
def handle_copy_error(file_or_folder_name, error, drive_service=None):
    """
    Logs the error message and retrieves the parent folder(s) of the file if possible.

    Args:
        file_or_folder_name (str): The name of the file or folder that failed to copy.
        error (Exception): The error that occurred while copying the file or folder.
        drive_service: The Google Drive service object (optional, uses global if not provided).
    """
    svc = drive_service or service
    # If the error is related to copying a file, try to retrieve its parent folder(s)
    if isinstance(error, HttpError) and "fileId" in error.__dict__:
        file_id = error.__dict__["fileId"]
        try:
            # Retrieve the file's metadata to get parent folder(s)
            file_metadata = svc.files().get(fileId=file_id, fields="parents").execute()
            parent_folder_ids = file_metadata.get("parents", [])
            # Construct URLs to the parent folders based on their IDs
            for folder_id in parent_folder_ids:
                folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
                logging.error("Folder URL: %s", folder_url)
        except HttpError as error_msg:
            logging.error("ERROR-PARENT: %s", error_msg)

    # Write the error to the log file
    logging.error("COPY FAILED: %s: %s", file_or_folder_name, error)


# Define a function to recursively add child records to the CSV
def add_child_folders(folder_id, writer, drive_service=None):
    """
    Recursively adds child folders to the CSV file.

    Args:
        folder_id (str): The ID of the folder to add child folders for.
        writer: The CSV writer object.
        drive_service: The Google Drive service object (optional, uses global if not provided).
    """
    svc = drive_service or service
    query = (
        f"'{folder_id}' in parents and "
        f"mimeType = '{MIME_FOLDER}' and "
        f"trashed = false"
    )
    results = svc.files().list(q=query, orderBy="name asc").execute()
    folders = results.get("files", [])
    for folder in folders:
        folder_id = folder["id"]
        num_files, num_folders = count_child_objects(folder_id, svc)
        writer.writerow([folder["name"], num_files, num_folders])


# Enable pylint for no-member again
# pylint: enable=no-member


# pylint: disable=no-member
def _list_files_recursive(folder_id, drive_service=None, path_prefix=""):
    """
    Recursively list every non-folder file under folder_id.

    Returns a list of dicts: {"name", "size", "mimeType", "path"}. "size" is the
    string byte-size Drive reports for binary files/uploads; Google-native files
    (Docs, Sheets, Slides, Forms, Drawings) have no size and are reported as None
    since they have no meaningful byte size to compare for duplicate detection.
    """
    svc = drive_service or service
    query = f"'{folder_id}' in parents and trashed = false"
    results = (
        svc.files()
        .list(q=query, fields="files(id,name,mimeType,size)")
        .execute()
    )
    items = results.get("files", [])

    files = []
    for item in items:
        item_path = f"{path_prefix}{item.get('name', '')}"
        if item.get("mimeType") == MIME_FOLDER:
            files.extend(
                _list_files_recursive(item["id"], svc, path_prefix=f"{item_path}/")
            )
        else:
            files.append(
                {
                    "name": item.get("name"),
                    "size": item.get("size"),
                    "mimeType": item.get("mimeType"),
                    "path": item_path,
                }
            )
    return files


# pylint: enable=no-member


def find_duplicate_files(src_folder_id, dest_folder_id, drive_service=None):
    """
    Find files with an identical name and byte size present in both the source
    and destination folder trees.

    Google-native files (Docs, Sheets, Slides, ...) have no byte size and are
    excluded from comparison -- matching on name alone would produce false
    positives for any two documents that happen to share a name.

    Returns a list of dicts sorted by name: {"name", "size", "source_path",
    "destination_path"}. A source file matching multiple destination files
    (or vice versa) produces one row per matching pair.
    """
    svc = drive_service or service
    src_files = _list_files_recursive(src_folder_id, svc)
    dest_files = _list_files_recursive(dest_folder_id, svc)

    dest_index = {}
    for dest_file in dest_files:
        if not dest_file["size"]:
            continue
        key = (dest_file["name"], dest_file["size"])
        dest_index.setdefault(key, []).append(dest_file)

    duplicates = []
    for src_file in src_files:
        if not src_file["size"]:
            continue
        key = (src_file["name"], src_file["size"])
        for match in dest_index.get(key, []):
            duplicates.append(
                {
                    "name": src_file["name"],
                    "size": src_file["size"],
                    "source_path": src_file["path"],
                    "destination_path": match["path"],
                }
            )

    duplicates.sort(key=lambda d: (d["name"], d["source_path"]))
    return duplicates


def write_duplicate_report(duplicates, csv_path=DUPLICATE_REPORT_PATH):
    """
    Write a duplicate-detection report to csv_path.

    Args:
        duplicates (list): Rows from find_duplicate_files().
        csv_path (str): Destination CSV file path.

    Returns:
        str: The csv_path that was written.
    """
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["File Name", "Size (bytes)", "Source Path", "Destination Path"])
        for dup in duplicates:
            writer.writerow(
                [dup["name"], dup["size"], dup["source_path"], dup["destination_path"]]
            )
    return csv_path


# Compare the two assessments CSV files
def compare_csv_files(file1, file2):
    """
    Compare two CSV files and log whether they are equal or not.

    Args:
        file1 (str): The path to the first CSV file.
        file2 (str): The path to the second CSV file.
    """
    # Read the CSV files into pandas DataFrames
    assessment2 = pd.read_csv(file1)
    assessment3 = pd.read_csv(file2)

    # Check if the DataFrames are equal
    if assessment2.equals(assessment3):
        logging.info("VALIDATION SUCCESSFUL!")
    else:
        logging.error(
            "VALIDATION FAILED - Source & Destination folder counts do not match."
        )
        print("ERROR: VALIDATION FAILED!")


def main(argv=None):
    """Main entry point for CLI."""
    global service  # pylint: disable=global-statement

    parser = argparse.ArgumentParser(
        prog="drive-copy",
        description="Google Drive report and copy utility",
    )
    parser.add_argument(
        "--help-env",
        action="store_true",
        help="Show required environment variables and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview source counts and planned copy target without writing outputs or copying files",
    )
    parser.add_argument(
        "--include-mime",
        metavar="MIME",
        help=(
            "Comma-separated MIME type patterns to include "
            "(aliases: docs, sheets, slides, forms, drawings, pdf, images, text, video, audio, zip). "
            "Prefix patterns ending in '/' match all subtypes (e.g. 'image/')."
        ),
    )
    parser.add_argument(
        "--exclude-mime",
        metavar="MIME",
        help="Comma-separated MIME type patterns to exclude (same aliases as --include-mime).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        metavar="N",
        help=f"Number of parallel copy workers (default: {DEFAULT_WORKERS}; 1 = sequential).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        metavar="N",
        help="Maximum retry attempts per file copy with exponential backoff (default: 1).",
    )
    parser.add_argument(
        "--max-backoff",
        type=float,
        default=DEFAULT_MAX_BACKOFF,
        metavar="SECONDS",
        help=f"Maximum exponential backoff delay in seconds (default: {DEFAULT_MAX_BACKOFF}).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Skip files and folders that already exist in the destination "
            "(enables safe re-runs after partial failures)."
        ),
    )
    parser.add_argument(
        "--mirror-permissions",
        action="store_true",
        help=(
            "Copy sharing/ACL permissions from each source file and folder onto its "
            "destination counterpart as it is copied/created (ownership is never "
            "transferred). Requires the drive scope's write access to permissions."
        ),
    )
    parser.add_argument(
        "--duplicate-report",
        action="store_true",
        help=(
            "Scan the source and destination folders for files with identical name "
            f"and size, write {DUPLICATE_REPORT_PATH}, then exit without copying. "
            "Can be run before a copy (to spot pre-existing overlap) or after one "
            "(to spot redundant copies)."
        ),
    )
    args, _ = parser.parse_known_args(argv)

    if args.help_env:
        print("Required environment variables:")
        print(f"- {CLIENT_ID_ENV_VAR}")
        print(f"- {SOURCE_FOLDER_ID_ENV_VAR}")
        print(f"- {DESTINATION_FOLDER_ID_ENV_VAR}")
        return

    include_mime = (
        _resolve_mime_aliases(
            [t.strip() for t in args.include_mime.split(",") if t.strip()]
        )
        if args.include_mime
        else []
    )
    exclude_mime = (
        _resolve_mime_aliases(
            [t.strip() for t in args.exclude_mime.split(",") if t.strip()]
        )
        if args.exclude_mime
        else []
    )

    if not args.dry_run:
        # Ensure the outputs directory exists and attach the file log handler.
        # This is done here (not at module level) to avoid FileNotFoundError on import
        # when the directory does not yet exist (the original RCA for CI failures).
        os.makedirs(OUTPUTS_DIRECTORY, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        log_file_path = os.path.join(OUTPUTS_DIRECTORY, f"gcp-{timestamp}.log")
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setFormatter(logging.Formatter(LOG_FILE_FORMAT))
        logging.getLogger().addHandler(file_handler)

    print("Google Drive Report & Copy Tool")
    print("Running copy_folder script...")

    # Read environment variables
    client_id_file = os.environ.get(CLIENT_ID_ENV_VAR)
    source_folder_id = os.environ.get(SOURCE_FOLDER_ID_ENV_VAR)
    destination_folder_id = os.environ.get(DESTINATION_FOLDER_ID_ENV_VAR)

    # Check if the environment variables are set
    if not client_id_file:
        raise ValueError(
            f"{MISSING_ENVAR_TXT} Google Drive API Client ID JSON: {CLIENT_ID_ENV_VAR}"
        )
    if not source_folder_id:
        raise ValueError(
            f"{MISSING_ENVAR_TXT} Source folder ID: {SOURCE_FOLDER_ID_ENV_VAR}"
        )
    if not destination_folder_id:
        raise ValueError(
            f"{MISSING_ENVAR_TXT} Destination folder ID: {DESTINATION_FOLDER_ID_ENV_VAR}"
        )

    # Authenticate and authorize the user
    authed_credentials = authenticate_and_authorize(client_id_file, SCOPES)

    # Check if credentials are valid
    if authed_credentials:
        service = create_drive_service(authed_credentials)
    else:
        logging.error("Authorization failed.")
        raise RuntimeError("Failed to authenticate with Google Drive API")

    # Get folder names
    # pylint: disable=no-member
    source_folder_name = (
        service.files().get(fileId=source_folder_id, fields="name").execute()
    )
    destination_folder_name = (
        service.files().get(fileId=destination_folder_id, fields="name").execute()
    )
    # pylint: enable=no-member

    if args.duplicate_report:
        print(
            f"Scanning for duplicate files between '{source_folder_name['name']}'"
            f" and '{destination_folder_name['name']}'..."
        )
        duplicates = find_duplicate_files(source_folder_id, destination_folder_id, service)
        report_path = write_duplicate_report(duplicates)
        print(
            f"Duplicate report written to {report_path}"
            f" ({len(duplicates)} matching file(s) found)."
        )
        logging.info(
            "DUPLICATE REPORT: %d matching file(s) written to %s",
            len(duplicates),
            report_path,
        )
        return

    total_num_files, total_num_folders = count_child_objects(
        source_folder_id, service, include_mime=include_mime, exclude_mime=exclude_mime
    )

    if args.dry_run:
        filter_note = ""
        if include_mime:
            filter_note += f" [include: {', '.join(include_mime)}]"
        if exclude_mime:
            filter_note += f" [exclude: {', '.join(exclude_mime)}]"
        print(
            "DRY RUN: no files will be copied and no output artifacts will be written."
        )
        print(
            f"Source '{source_folder_name['name']}'"
            f" -> Destination '{destination_folder_name['name']}'"
        )
        print(
            f"Planned object scan: files={total_num_files},"
            f" folders={total_num_folders}{filter_note}"
        )
        if args.workers > 1:
            print(f"Parallel copy enabled: {args.workers} workers")
        if args.mirror_permissions:
            print("Permission mirroring enabled: ACL/sharing settings will be copied")
        logging.info(
            "DRY RUN: source=%s destination=%s files=%d folders=%d",
            source_folder_name["name"],
            destination_folder_name["name"],
            total_num_files,
            total_num_folders,
        )
        return

    logging.info("STARTING ASSESSMENTS...")
    if include_mime:
        logging.info("MIME include filter: %s", include_mime)
    if exclude_mime:
        logging.info("MIME exclude filter: %s", exclude_mime)
    if args.workers > 1:
        logging.info("Parallel copy: %d workers", args.workers)
    if args.skip_existing:
        logging.info("Skip-existing mode: files/folders already in destination will be skipped")
    if args.mirror_permissions:
        logging.info("Mirror-permissions mode: source ACL/sharing settings will be copied to destination")

    # ASSESSMENT 1 - Write the results to a CSV file
    csv_file = "./outputs/assessment-1.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["Folder Name", "Number of Files", "Number of Folders"])
        writer.writerow(
            [source_folder_name["name"], total_num_files, total_num_folders]
        )

    # ASSESSMENT 2 - Write the results to a CSV file
    csv_file = "./outputs/assessment-2.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["Folder Name", "Number of Files", "Number of Child Folders"])
        # Write the Total at the top of the CSV
        total_num_files, total_num_folders = count_child_objects(
            source_folder_id, service, include_mime=include_mime, exclude_mime=exclude_mime
        )
        writer.writerow(["TOTAL", total_num_files, total_num_folders])
        add_child_folders(source_folder_id, writer, service)

    # Copy all child objects (including nested folders and files) to the new top-level folder
    logging.info("STARTING COPY TO %s...", destination_folder_name["name"])
    copy_child_objects(
        source_folder_id,
        destination_folder_id,
        service,
        max_retries=args.max_retries,
        max_backoff=args.max_backoff,
        workers=args.workers,
        include_mime=include_mime,
        exclude_mime=exclude_mime,
        skip_existing=args.skip_existing,
        mirror_permissions=args.mirror_permissions,
    )
    logging.info("COPY COMPLETED!")

    # ASSESSMENT 3 - Write the results to a CSV file
    csv_file = "./outputs/assessment-3.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["Folder Name", "Number of Files", "Number of Child Folders"])
        # Write the Total at the top of the CSV
        total_num_files, total_num_folders = count_child_objects(
            destination_folder_id, service
        )
        writer.writerow(["TOTAL", total_num_files, total_num_folders])
        add_child_folders(destination_folder_id, writer, service)

    logging.info("ASSESSMENTS COMPLETED!")

    logging.info("STARTING VALIDATION...")
    # Load source and destination file count CSV reports
    output_2 = "./outputs/assessment-2.csv"
    output_3 = "./outputs/assessment-3.csv"

    compare_csv_files(output_2, output_3)

    # FINISH SCRIPT
    logging.info(
        "COPIED: %s to %s", source_folder_name["name"], destination_folder_name["name"]
    )
    print("SCRIPT COMPLETED!")


if __name__ == "__main__":
    main()
