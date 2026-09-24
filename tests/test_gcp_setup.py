"""Unit tests for gcp/gcp_setup.py (GCP project provisioning wrapper).

Every gcloud invocation goes through subprocess.run, which is mocked here, so
no real gcloud/network calls are made. Interactive input() is patched too.
"""

# pylint: disable=redefined-outer-name,protected-access
import json
import subprocess
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gcp import gcp_setup as gs


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    """Build a fake subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args="cmd", returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture
def mock_run() -> Iterator[MagicMock]:
    """Patch subprocess.run inside gcp_setup and return the mock."""
    with patch("gcp.gcp_setup.subprocess.run") as mocked:
        mocked.return_value = _completed()
        yield mocked


# ── _redact_sensitive_cli_args / run_command ─────────────────────────────


class TestRedaction:
    """Sensitive CLI argument values must never be logged."""

    def test_redacts_billing_account(self):
        """Billing account IDs are replaced with [REDACTED]."""
        out = gs._redact_sensitive_cli_args(
            "gcloud billing projects link p --billing-account=0123-ABCD-4567"
        )
        assert "0123-ABCD-4567" not in out
        assert "--billing-account=[REDACTED]" in out

    def test_redacts_filter_projects(self):
        """Project IDs in --filter-projects are replaced with [REDACTED]."""
        out = gs._redact_sensitive_cli_args(
            "gcloud billing budgets create --filter-projects=projects/my-proj"
        )
        assert "my-proj" not in out
        assert "--filter-projects=projects/[REDACTED]" in out

    def test_leaves_other_args_untouched(self):
        """Commands without sensitive args pass through unchanged."""
        cmd = "gcloud services enable drive.googleapis.com --project=p1"
        assert gs._redact_sensitive_cli_args(cmd) == cmd


class TestRunCommand:
    """run_command wraps subprocess.run and reports failures."""

    def test_success_returns_result(self, mock_run):
        """A zero exit returns the CompletedProcess and forwards kwargs."""
        mock_run.return_value = _completed(stdout="ok")
        res = gs.run_command("gcloud version", input_data="y")
        assert res.stdout == "ok"
        _, kwargs = mock_run.call_args
        assert kwargs["input"] == "y"
        assert kwargs["check"] is False

    def test_failure_with_check_returns_none_and_redacts(self, mock_run, capsys):
        """A non-zero exit with check=True returns None and logs a redacted command."""
        mock_run.return_value = _completed(returncode=1, stdout=" o ", stderr=" e ")
        res = gs.run_command("gcloud x --billing-account=SECRET-ID")
        assert res is None
        out = capsys.readouterr().out
        assert "SECRET-ID" not in out
        assert "[REDACTED]" in out
        assert "stdout: o" in out
        assert "stderr: e" in out

    def test_failure_without_check_returns_result(self, mock_run):
        """With check=False a non-zero result is returned to the caller."""
        mock_run.return_value = _completed(returncode=2)
        res = gs.run_command("gcloud x", check=False)
        assert res.returncode == 2

    def test_exception_returns_none(self, mock_run, capsys):
        """Exceptions from subprocess.run are caught and reported."""
        mock_run.side_effect = OSError("boom")
        assert gs.run_command("gcloud x") is None
        assert "boom" in capsys.readouterr().out


# ── Simple helpers ───────────────────────────────────────────────────────


class TestHelpers:
    """Project ID generation, gcloud detection and account lookup."""

    def test_generate_project_id_format(self):
        """Generated IDs are 'ws-auth-' plus six lowercase alphanumerics."""
        pid = gs.generate_project_id()
        assert pid.startswith("ws-auth-")
        suffix = pid[len("ws-auth-") :]
        assert len(suffix) == 6
        assert all(c.islower() or c.isdigit() for c in suffix)

    @pytest.mark.parametrize(
        "which, expected", [("/usr/bin/gcloud", True), (None, False)]
    )
    def test_check_gcloud_installed(self, which, expected):
        """gcloud detection follows shutil.which."""
        with patch("gcp.gcp_setup.shutil.which", return_value=which):
            assert gs.check_gcloud_installed() is expected

    def test_get_gcloud_account_returns_stripped(self, mock_run):
        """The active account is returned without surrounding whitespace."""
        mock_run.return_value = _completed(stdout="me@example.com\n")
        assert gs.get_gcloud_account() == "me@example.com"

    @pytest.mark.parametrize("rc, stdout", [(0, "  \n"), (1, "me@example.com")])
    def test_get_gcloud_account_none(self, mock_run, rc, stdout):
        """Blank output or a failed command means no active account."""
        mock_run.return_value = _completed(returncode=rc, stdout=stdout)
        assert gs.get_gcloud_account() is None

    def test_get_gcloud_account_exception(self, mock_run):
        """A subprocess exception means no active account."""
        mock_run.side_effect = OSError
        assert gs.get_gcloud_account() is None


# ── Billing ──────────────────────────────────────────────────────────────


MENU_ENTRIES = [
    {"displayName": "Main", "name": "billingAccounts/AAA-111"},
    {"displayName": "Side", "name": "billingAccounts/BBB-222"},
]


class TestListBillingAccounts:
    """list_billing_accounts parses gcloud JSON output."""

    def test_parses_json(self, mock_run):
        """Valid JSON output is returned as a list of dicts."""
        mock_run.return_value = _completed(stdout=json.dumps(MENU_ENTRIES))
        assert gs.list_billing_accounts() == MENU_ENTRIES

    def test_invalid_json_returns_empty(self, mock_run):
        """Unparseable output yields an empty list."""
        mock_run.return_value = _completed(stdout="not json")
        assert gs.list_billing_accounts() == []

    def test_nonzero_returns_empty(self, mock_run):
        """A failed command yields an empty list."""
        mock_run.return_value = _completed(
            returncode=1, stdout=json.dumps(MENU_ENTRIES)
        )
        assert gs.list_billing_accounts() == []


class TestSelectBillingAccount:
    """select_billing_account supports numeric choice or manual entry."""

    def test_numeric_choice(self, capsys):
        """A valid menu number selects that account's short ID."""
        with patch("builtins.input", return_value=" 2 "):
            assert gs.select_billing_account(MENU_ENTRIES) == "BBB-222"
        out = capsys.readouterr().out
        assert "[1] Main  (AAA-111)" in out
        assert "[2] Side  (BBB-222)" in out

    @pytest.mark.parametrize("choice", ["0", "3", "CCC-333"])
    def test_out_of_range_or_manual_returned_verbatim(self, choice):
        """Out-of-range numbers and free text are returned as typed."""
        with patch("builtins.input", return_value=choice):
            assert gs.select_billing_account(MENU_ENTRIES) == choice

    def test_missing_fields_default(self, capsys):
        """Accounts missing displayName/name fall back to defaults."""
        with patch("builtins.input", return_value="1"):
            assert gs.select_billing_account([{}]) == ""
        assert "Unnamed" in capsys.readouterr().out

    def test_no_accounts_prompts_manual(self, capsys):
        """With no accounts the user is prompted for a manual ID."""
        with patch("builtins.input", return_value="  XYZ-1  "):
            assert gs.select_billing_account([]) == "XYZ-1"
        assert "No billing accounts found" in capsys.readouterr().out


# ── Project / billing link / APIs / budget ───────────────────────────────


class TestProjectProvisioning:
    """create_project, link_billing, enable_apis and create_budget."""

    def test_create_project_success(self, mock_run):
        """A successful gcloud call returns True."""
        assert gs.create_project("proj-1") is True
        cmd = mock_run.call_args[0][0]
        assert cmd.startswith("gcloud projects create proj-1")

    def test_create_project_failure(self, mock_run):
        """A failed gcloud call returns False."""
        mock_run.return_value = _completed(returncode=1)
        assert gs.create_project("proj-1") is False

    def test_link_billing_success(self, mock_run, capsys):
        """The billing ID is passed to gcloud but never printed."""
        gs.link_billing("proj-1", "BILL-SECRET")
        assert "--billing-account=BILL-SECRET" in mock_run.call_args[0][0]
        out = capsys.readouterr().out
        assert "BILL-SECRET" not in out
        assert "WARNING" not in out

    def test_link_billing_failure_warns(self, mock_run, capsys):
        """A failed link prints a manual-linking warning."""
        mock_run.return_value = _completed(returncode=1)
        gs.link_billing("proj-1", "BILL")
        assert "Could not link billing" in capsys.readouterr().out

    def test_link_billing_exception_warns(self, mock_run, capsys):
        """A subprocess exception also prints the warning."""
        mock_run.side_effect = OSError
        gs.link_billing("proj-1", "BILL")
        assert "Could not link billing" in capsys.readouterr().out

    def test_enable_apis_success(self, mock_run, capsys):
        """All required APIs are enabled in one gcloud call."""
        gs.enable_apis("proj-1")
        cmd = mock_run.call_args[0][0]
        apis = {tok for tok in cmd.split() if tok.endswith(".googleapis.com")}
        assert apis == {
            f"{name}.googleapis.com"
            for name in ("gmail", "calendar-json", "drive")
            + ("generativelanguage", "billingbudgets")
        }
        assert cmd.endswith("--project=proj-1")
        assert "APIs enabled successfully" in capsys.readouterr().out

    def test_enable_apis_failure_exits(self, mock_run):
        """Failure to enable APIs exits with status 1."""
        mock_run.return_value = _completed(returncode=1)
        with pytest.raises(SystemExit) as exc:
            gs.enable_apis("proj-1")
        assert exc.value.code == 1

    def test_create_budget_success(self, mock_run, capsys):
        """The budget command carries amount, thresholds and project filter."""
        gs.create_budget("proj-1", "BILL")
        cmd = mock_run.call_args[0][0]
        assert "--billing-account=BILL" in cmd
        assert "--budget-amount=50.00USD" in cmd
        assert "--threshold-rule=percent=0.5" in cmd
        assert "--threshold-rule=percent=0.9" in cmd
        assert "--filter-projects=projects/proj-1" in cmd
        assert "Budget alert created" in capsys.readouterr().out

    def test_create_budget_failure_warns(self, mock_run, capsys):
        """A failed budget creation prints a warning."""
        mock_run.return_value = _completed(returncode=1)
        gs.create_budget("proj-1", "BILL")
        assert "Budget creation failed" in capsys.readouterr().out


# ── OAuth client creation ────────────────────────────────────────────────


def _dispatch(
    responses: dict[str, subprocess.CompletedProcess],
) -> Callable[..., subprocess.CompletedProcess]:
    """Return a subprocess.run side effect keyed on a command substring."""

    def _side_effect(command: str, **_kwargs: Any) -> subprocess.CompletedProcess:
        for key, value in responses.items():
            if key in command:
                return value
        raise AssertionError(f"unexpected command: {command}")

    return _side_effect


CLIENT_OK = _completed(stdout=json.dumps({"clientId": "cid", "clientSecret": "csec"}))


class TestTryCreateOauthClient:
    """try_create_oauth_client creates/locates a brand then a web client."""

    def test_brand_created_then_client(self, mock_run):
        """A newly created brand is used to create the web client."""
        mock_run.side_effect = _dispatch(
            {
                "oauth-brands create": _completed(
                    stdout=json.dumps({"name": "brands/1"})
                ),
                "oauth-clients create": CLIENT_OK,
            }
        )
        assert gs.try_create_oauth_client("p", "me@x.com") == {
            "client_id": "cid",
            "client_secret": "csec",
        }
        cmds = [c[0][0] for c in mock_run.call_args_list]
        assert "--support-email=me@x.com" in cmds[0]
        assert "--brand=brands/1" in cmds[1]
        assert not any("oauth-brands list" in c for c in cmds)

    @pytest.mark.parametrize(
        "create_res",
        [_completed(returncode=1), _completed(stdout="{bad json")],
    )
    def test_falls_back_to_existing_brand(self, mock_run, create_res):
        """If brand creation fails, the first listed brand is used."""
        mock_run.side_effect = _dispatch(
            {
                "oauth-brands create": create_res,
                "oauth-brands list": _completed(
                    stdout=json.dumps([{"name": "brands/9"}])
                ),
                "oauth-clients create": CLIENT_OK,
            }
        )
        assert gs.try_create_oauth_client("p", "a")["client_id"] == "cid"
        assert "--brand=brands/9" in mock_run.call_args_list[-1][0][0]

    @pytest.mark.parametrize(
        "list_res",
        [
            _completed(returncode=1),
            _completed(stdout="[]"),
            _completed(stdout="not json"),
        ],
    )
    def test_no_brand_returns_none(self, mock_run, list_res):
        """Without any brand no client is created and None is returned."""
        mock_run.side_effect = _dispatch(
            {
                "oauth-brands create": _completed(returncode=1),
                "oauth-brands list": list_res,
            }
        )
        assert gs.try_create_oauth_client("p", "a") is None
        assert not any("oauth-clients" in c[0][0] for c in mock_run.call_args_list)

    @pytest.mark.parametrize(
        "client_res", [_completed(returncode=1), _completed(stdout="not json")]
    )
    def test_client_creation_failure_returns_none(self, mock_run, client_res):
        """A failed or unparseable client creation returns None."""
        mock_run.side_effect = _dispatch(
            {
                "oauth-brands create": _completed(
                    stdout=json.dumps({"name": "brands/1"})
                ),
                "oauth-clients create": client_res,
            }
        )
        assert gs.try_create_oauth_client("p", "a") is None


# ── client_secrets.json / manual steps ───────────────────────────────────


class TestWriteClientSecrets:
    """write_client_secrets emits a standard Google web client JSON."""

    def test_writes_expected_json(self, tmp_path, capsys):
        """The file contains the web client block with the given values."""
        out = tmp_path / "client_secrets.json"
        gs.write_client_secrets("proj-1", "cid", "csec", out)
        data = json.loads(out.read_text(encoding="utf-8"))
        web = data["web"]
        assert web["client_id"] == "cid"
        assert web["client_secret"] == "csec"
        assert web["project_id"] == "proj-1"
        assert web["token_uri"] == "https://oauth2.googleapis.com/token"
        assert web["redirect_uris"] == ["http://localhost:3000/oauth2callback"]
        assert str(out) in capsys.readouterr().out


def test_print_manual_oauth_steps(capsys):
    """Manual instructions include the console URL and support email."""
    gs.print_manual_oauth_steps("proj-1", "me@x.com")
    out = capsys.readouterr().out
    assert "https://console.cloud.google.com/apis/credentials?project=proj-1" in out
    assert "Support email: me@x.com" in out
    assert "apps/client_secrets.json" in out


# ── main() ───────────────────────────────────────────────────────────────


@pytest.fixture
def main_env(tmp_path: Path) -> Iterator[dict[str, Any]]:
    """Patch every side-effecting collaborator of main() and yield the mocks.

    __file__ is redirected into tmp_path so main() writes client_secrets.json
    under tmp_path/apps instead of the real repo.
    """
    fake_file = tmp_path / "gcp" / "gcp_setup.py"
    names = [
        "check_gcloud_installed",
        "get_gcloud_account",
        "run_command",
        "list_billing_accounts",
        "select_billing_account",
        "generate_project_id",
        "create_project",
        "link_billing",
        "enable_apis",
        "create_budget",
        "try_create_oauth_client",
        "write_client_secrets",
        "print_manual_oauth_steps",
    ]
    patchers = [patch(f"gcp.gcp_setup.{n}") for n in names]
    patchers.append(patch("gcp.gcp_setup.__file__", str(fake_file)))
    patchers.append(patch("builtins.input", return_value=""))
    with ExitStack() as stack:
        mocks: dict[str, Any] = {}
        for name, patcher in zip(names + ["__file__", "input"], patchers):
            mocks[name] = stack.enter_context(patcher)
        mocks["check_gcloud_installed"].return_value = True
        mocks["get_gcloud_account"].return_value = "me@x.com"
        mocks["select_billing_account"].return_value = "BILL"
        mocks["generate_project_id"].return_value = "ws-auth-abc123"
        mocks["create_project"].return_value = True
        mocks["try_create_oauth_client"].return_value = {
            "client_id": "cid",
            "client_secret": "csec",
        }
        mocks["out_path"] = tmp_path / "apps" / "client_secrets.json"
        yield mocks


class TestMain:
    """End-to-end orchestration of main() with all collaborators mocked."""

    def test_happy_path_writes_real_credentials(self, main_env):
        """Full run provisions the project and writes real credentials."""
        gs.main()
        main_env["create_project"].assert_called_once_with("ws-auth-abc123")
        main_env["link_billing"].assert_called_once_with("ws-auth-abc123", "BILL")
        main_env["enable_apis"].assert_called_once_with("ws-auth-abc123")
        main_env["create_budget"].assert_called_once_with("ws-auth-abc123", "BILL")
        main_env["write_client_secrets"].assert_called_once_with(
            "ws-auth-abc123", "cid", "csec", main_env["out_path"]
        )
        main_env["print_manual_oauth_steps"].assert_not_called()
        assert main_env["out_path"].parent.is_dir()

    def test_custom_project_id_from_input(self, main_env):
        """A typed project ID overrides the generated default."""
        main_env["input"].return_value = "  my-proj  "
        gs.main()
        main_env["create_project"].assert_called_once_with("my-proj")

    @pytest.mark.parametrize(
        "creds", [None, {"client_id": "cid", "client_secret": None}]
    )
    def test_oauth_fallback_writes_placeholder(self, main_env, creds):
        """Missing OAuth creds print manual steps and write a placeholder."""
        main_env["try_create_oauth_client"].return_value = creds
        gs.main()
        main_env["print_manual_oauth_steps"].assert_called_once_with(
            "ws-auth-abc123", "me@x.com"
        )
        args = main_env["write_client_secrets"].call_args[0]
        assert args[1] == "YOUR_CLIENT_ID.apps.googleusercontent.com"
        assert args[2] == "YOUR_CLIENT_SECRET"

    def test_login_when_no_session(self, main_env):
        """With no session, gcloud auth login is run and the account re-read."""
        main_env["get_gcloud_account"].side_effect = [None, "me@x.com"]
        gs.main()
        main_env["run_command"].assert_called_once_with("gcloud auth login")
        main_env["create_project"].assert_called_once()

    def test_gcloud_missing_exits(self, main_env):
        """Missing gcloud exits before any other work."""
        main_env["check_gcloud_installed"].return_value = False
        with pytest.raises(SystemExit):
            gs.main()
        main_env["get_gcloud_account"].assert_not_called()

    def test_auth_failure_exits(self, main_env):
        """Failed authentication exits before billing lookup."""
        main_env["get_gcloud_account"].return_value = None
        with pytest.raises(SystemExit):
            gs.main()
        main_env["list_billing_accounts"].assert_not_called()

    def test_missing_billing_exits(self, main_env):
        """An empty billing ID exits before project creation."""
        main_env["select_billing_account"].return_value = ""
        with pytest.raises(SystemExit):
            gs.main()
        main_env["create_project"].assert_not_called()

    def test_project_creation_failure_exits(self, main_env):
        """Failed project creation exits before billing is linked."""
        main_env["create_project"].return_value = False
        with pytest.raises(SystemExit):
            gs.main()
        main_env["link_billing"].assert_not_called()
