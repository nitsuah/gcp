"""
gcp_setup.py — GCP Project Provisioning Wrapper

Automates creation and baseline configuration of a new GCP project for
multi-account Google Workspace OAuth integrations (Overseer, Auto-Apply,
AgentBoard). Enables Gmail, Calendar, Drive, and Gemini APIs, configures
budget alerts, and outputs OAuth 2.0 client credentials.
"""

import subprocess
import json
import sys
import re
import random
import string
import shutil
from pathlib import Path


def _redact_sensitive_cli_args(command):
    """Redact sensitive CLI argument values before logging."""
    redacted = re.sub(r"(--billing-account=)(\S+)", r"\1[REDACTED]", command)
    redacted = re.sub(r"(--filter-projects=projects/)(\S+)", r"\1[REDACTED]", redacted)
    return redacted


def run_command(command, check=True, input_data=None):
    """Run a CLI command and return the result."""
    try:
        result = subprocess.run(  # nosec B602
            command,
            shell=True,
            text=True,
            capture_output=True,
            input=input_data,
        )
        if check and result.returncode != 0:
            print(f"[ERROR] Command failed: {_redact_sensitive_cli_args(command)}")
            print(f"  stdout: {result.stdout.strip()}")
            print(f"  stderr: {result.stderr.strip()}")
            return None
        return result
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[ERROR] Exception running command: {exc}")
        return None


def generate_project_id():
    """Return a random RFC-compliant GCP project ID."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"ws-auth-{suffix}"


def check_gcloud_installed():
    """Return True if gcloud CLI is on PATH."""
    return shutil.which("gcloud") is not None


def get_gcloud_account():
    """Return the active gcloud account, or None if unauthenticated."""
    res = run_command("gcloud config get-value account", check=False)
    if res and res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip()
    return None


def list_billing_accounts():
    """Return a list of billing account dicts, or empty list on failure."""
    res = run_command("gcloud billing accounts list --format=json", check=False)
    if res and res.returncode == 0:
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError:
            pass
    return []


def select_billing_account(billing_accounts):
    """Interactively select or manually enter a billing account ID."""
    if billing_accounts:
        print("\nAvailable billing accounts:")
        for idx, account in enumerate(billing_accounts):
            name = account.get("displayName", "Unnamed")
            ba_id = account.get("name", "").split("/")[-1]
            print(f"  [{idx + 1}] {name}  ({ba_id})")

        choice = input(
            f"\nSelect billing account (1–{len(billing_accounts)}) "
            "or paste a Billing ID manually: "
        ).strip()

        if choice.isdigit() and 1 <= int(choice) <= len(billing_accounts):
            return billing_accounts[int(choice) - 1].get("name", "").split("/")[-1]
        return choice

    print("[WARNING] No billing accounts found automatically.")
    return input("Enter your GCP Billing Account ID (e.g. 012345-ABCDEF-123456): ").strip()


def create_project(project_id):
    """Create a new GCP project and return True on success."""
    print(f"\n[INFO] Creating GCP project '{project_id}'…")
    res = run_command(
        f'gcloud projects create {project_id} --name="Workspace Automation Hub"'
    )
    return res is not None


def link_billing(project_id, billing_id):
    """Link billing account to the project."""
    masked = f"{'*' * max(len(billing_id) - 4, 0)}{billing_id[-4:]}" if billing_id else "<redacted>"
    print(f"[INFO] Linking billing account {masked} to {project_id}…")
    res = run_command(
        f"gcloud billing projects link {project_id} --billing-account={billing_id}",
        check=False,
    )
    if res is None or res.returncode != 0:
        print("[WARNING] Could not link billing automatically — link it manually in the Console.")


def enable_apis(project_id):
    """Enable all required GCP service APIs."""
    apis = [
        "gmail.googleapis.com",
        "calendar-json.googleapis.com",
        "drive.googleapis.com",
        "generativelanguage.googleapis.com",
        "billingbudgets.googleapis.com",
    ]
    print(f"\n[INFO] Enabling APIs: {', '.join(apis)}")
    res = run_command(
        f"gcloud services enable {' '.join(apis)} --project={project_id}"
    )
    if res is None:
        print("[ERROR] Failed to enable APIs. Verify billing is linked.")
        sys.exit(1)
    print("[INFO] APIs enabled successfully.")


def create_budget(project_id, billing_id):
    """Create a $50 budget alert with 50 % and 90 % thresholds."""
    print("\n[INFO] Creating budget alert ($50 USD / month)…")
    cmd = (
        f"gcloud billing budgets create "
        f"--billing-account={billing_id} "
        f'--display-name="Workspace Integration Budget" '
        f"--budget-amount=50.00USD "
        f"--threshold-rule=percent=0.5 "
        f"--threshold-rule=percent=0.9 "
        f"--filter-projects=projects/{project_id}"
    )
    res = run_command(cmd, check=False)
    if res and res.returncode == 0:
        print("[INFO] Budget alert created: 50 % and 90 % notifications active.")
    else:
        print("[WARNING] Budget creation failed — configure manually in the GCP Console.")


def try_create_oauth_client(project_id, account):
    """
    Attempt to create OAuth consent screen brand and web client via gcloud alpha.
    Returns a dict with {client_id, client_secret} on success, or None on failure.
    """
    # Step 1 — create or locate OAuth brand
    brand_name = None
    brand_cmd = (
        f"gcloud alpha apis oauth-brands create "
        f'--application-title="Workspace Hub" '
        f"--support-email={account} "
        f"--project={project_id} --format=json"
    )
    res = run_command(brand_cmd, check=False)
    if res and res.returncode == 0:
        try:
            brand_name = json.loads(res.stdout).get("name")
        except json.JSONDecodeError:
            pass

    if not brand_name:
        # Brand may already exist — list it
        list_res = run_command(
            f"gcloud alpha apis oauth-brands list --project={project_id} --format=json",
            check=False,
        )
        if list_res and list_res.returncode == 0:
            try:
                brands = json.loads(list_res.stdout)
                if brands:
                    brand_name = brands[0].get("name")
            except json.JSONDecodeError:
                pass

    if not brand_name:
        return None

    print(f"[INFO] OAuth brand: {brand_name}")

    # Step 2 — create the Web application client
    client_cmd = (
        f"gcloud alpha apis oauth-clients create "
        f'--display-name="Overseer Automation Client" '
        f"--brand={brand_name} "
        f"--project={project_id} "
        f'--redirect-uris="http://localhost:3000/oauth2callback" '
        f"--format=json"
    )
    res = run_command(client_cmd, check=False)
    if res and res.returncode == 0:
        try:
            info = json.loads(res.stdout)
            return {
                "client_id": info.get("clientId"),
                "client_secret": info.get("clientSecret"),
            }
        except json.JSONDecodeError:
            pass

    return None


def write_client_secrets(project_id, client_id, client_secret, out_path):
    """Write a standard Google client_secrets.json to out_path."""
    secrets = {
        "web": {
            "client_id": client_id,
            "project_id": project_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost:3000/oauth2callback"],
        }
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(secrets, fh, indent=2)
    print(f"[SUCCESS] client_secrets.json written to: {out_path}")


def print_manual_oauth_steps(project_id, account):
    """Print step-by-step manual OAuth setup instructions."""
    console_url = f"https://console.cloud.google.com/apis/credentials?project={project_id}"
    print("\n" + "─" * 66)
    print("  MANUAL STEP REQUIRED — OAuth Consent Screen & Client ID")
    print("─" * 66)
    print(f"\n  GCP Console URL:\n    {console_url}\n")
    print("  1. Click 'Configure Consent Screen' → choose 'External'.")
    print(f"     App name: Workspace Hub | Support email: {account}")
    print("     Scopes to add:")
    print("       • openid  • email")
    print("       • https://www.googleapis.com/auth/gmail.modify")
    print("       • https://www.googleapis.com/auth/calendar")
    print("       • https://www.googleapis.com/auth/drive.file")
    print(f"     Test users: add the emails you will connect.")
    print("\n  2. Go to 'Credentials' → '+ Create Credentials' →")
    print("     'OAuth Client ID' → Application type: 'Web application'.")
    print("     Authorized redirect URI: http://localhost:3000/oauth2callback")
    print("\n  3. Download the JSON → rename to 'client_secrets.json'")
    print("     → place it at:  apps/client_secrets.json")
    print("─" * 66 + "\n")


def main():
    """Entry point for the GCP project provisioning wrapper."""
    print("=" * 66)
    print("   Google Workspace — GCP Project Provisioning Wrapper")
    print("=" * 66)

    # ── Pre-flight ────────────────────────────────────────────────
    if not check_gcloud_installed():
        print("[ERROR] gcloud CLI not found on PATH.")
        print("  Install via:  winget install Google.CloudSDK")
        print("  Or via Docker: docker compose run --rm gcp-setup")
        sys.exit(1)

    account = get_gcloud_account()
    if not account:
        print("[INFO] No active gcloud session. Launching login…")
        run_command("gcloud auth login")
        account = get_gcloud_account()
        if not account:
            print("[ERROR] Authentication failed.")
            sys.exit(1)
    print(f"[INFO] Authenticated as: {account}")

    # ── Billing ───────────────────────────────────────────────────
    billing_accounts = list_billing_accounts()
    billing_id = select_billing_account(billing_accounts)
    if not billing_id:
        print("[ERROR] Billing Account ID is required.")
        sys.exit(1)

    # ── Project ───────────────────────────────────────────────────
    default_id = generate_project_id()
    project_id = input(
        f"\nProject ID [Enter to accept '{default_id}']: "
    ).strip() or default_id

    if not create_project(project_id):
        print("[ERROR] Project creation failed.")
        sys.exit(1)

    link_billing(project_id, billing_id)
    enable_apis(project_id)
    create_budget(project_id, billing_id)

    # ── OAuth Credentials ─────────────────────────────────────────
    print("\n[INFO] Attempting automated OAuth client creation…")
    out_path = Path(__file__).parent.parent / "apps" / "client_secrets.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    creds = try_create_oauth_client(project_id, account)
    if creds and creds.get("client_id") and creds.get("client_secret"):
        write_client_secrets(project_id, creds["client_id"], creds["client_secret"], out_path)
    else:
        print("[WARNING] Automated OAuth client creation not available for this account type.")
        print_manual_oauth_steps(project_id, account)
        # Write placeholder so apps/server.js can detect the missing file
        write_client_secrets(
            project_id,
            "YOUR_CLIENT_ID.apps.googleusercontent.com",
            "YOUR_CLIENT_SECRET",
            out_path,
        )
        print("[INFO] Placeholder client_secrets.json written — replace after manual setup.")

    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 66)
    print(f"  Setup complete for project: {project_id}")
    print(f"  client_secrets.json location: {out_path}")
    print("=" * 66)


if __name__ == "__main__":
    main()
