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


GCLOUD_PATH = "C:/fake/bin/gcloud.CMD"


@pytest.fixture
def mock_run() -> Iterator[MagicMock]:
    """Patch subprocess.run inside gcp_setup and return the mock.

    shutil.which is pinned so the resolved gcloud path is deterministic
    whether or not the host has gcloud installed.
    """
    with patch("gcp.gcp_setup.subprocess.run") as mocked, patch(
        "gcp.gcp_setup.shutil.which", return_value=GCLOUD_PATH
    ):
        mocked.return_value = _completed()
        yield mocked


def _argv(mock_run: MagicMock, index: int = -1) -> list[str]:
    """Return the argument list passed to subprocess.run by the given call."""
    return mock_run.call_args_list[index].args[0]


# ── run_command


class TestRunCommand:
    """run_command wraps subprocess.run and reports failures."""

    def test_success_returns_result(self, mock_run):
        """A zero exit returns the CompletedProcess and forwards kwargs."""
        mock_run.return_value = _completed(stdout="ok")
        res = gs.run_command(["gcloud", "version"], input_data="y")
        assert res.stdout == "ok"
        assert _argv(mock_run) == [GCLOUD_PATH, "version"]
        _, kwargs = mock_run.call_args
        assert kwargs["input"] == "y"
        assert kwargs["check"] is False
        assert kwargs["shell"] is False

    def test_interactive_leaves_terminal_attached(self, mock_run: MagicMock) -> None:
        """interactive=True must not capture output, so login prompts stay visible."""
        gs.run_command(["gcloud", "auth", "login"], interactive=True)
        _, kwargs = mock_run.call_args
        assert "capture_output" not in kwargs
        assert "input" not in kwargs
        assert kwargs["shell"] is False

    def test_interactive_failure_skips_captured_output(
        self, mock_run: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """An interactive failure logs a safe gcloud failure without captured output."""
        mock_run.return_value = _completed(returncode=1, stdout=None, stderr=None)
        assert gs.run_command(["gcloud", "auth", "login"], interactive=True) is None
        assert "gcloud command failed" in caplog.text
        assert "gcloud auth login" not in caplog.text
        assert "stdout" not in caplog.text

    def test_failure_with_check_returns_none_and_omits_output(
        self, mock_run, caplog: pytest.LogCaptureFixture
    ):
        """Failure diagnostics omit command text and arbitrary captured output."""
        mock_run.return_value = _completed(
            returncode=1,
            stdout="stdout-secret-marker",
            stderr="stderr-secret-marker",
        )
        res = gs.run_command(["gcloud", "x", "--billing-account=SECRET-ID"])
        assert res is None
        assert "SECRET-ID" not in caplog.text
        assert "--billing-account" not in caplog.text
        assert "gcloud command failed" in caplog.text
        assert "exit 1" in caplog.text
        assert "stdout-secret-marker" not in caplog.text
        assert "stderr-secret-marker" not in caplog.text
        assert "omitted to avoid logging sensitive output" in caplog.text

    def test_failure_without_check_returns_result(self, mock_run):
        """With check=False a non-zero result is returned to the caller."""
        mock_run.return_value = _completed(returncode=2)
        res = gs.run_command(["gcloud", "x"], check=False)
        assert res.returncode == 2

    def test_exception_returns_none(
        self, mock_run, caplog: pytest.LogCaptureFixture
    ):
        """Exceptions are reported by type without logging command or message."""
        mock_run.side_effect = OSError("secret-bearing exception message")
        assert gs.run_command(["gcloud", "x", "--billing-account=SECRET-ID"]) is None
        assert "gcloud command raised" in caplog.text
        assert "OSError" in caplog.text
        assert "gcloud x" not in caplog.text
        assert "SECRET-ID" not in caplog.text
        assert "secret-bearing exception message" not in caplog.text

    def test_resolves_gcloud_to_full_path(self, mock_run):
        """args[0] 'gcloud' is replaced by the path shutil.which reports."""
        with patch("gcp.gcp_setup.shutil.which", return_value="C:/sdk/gcloud.cmd"):
            gs.run_command(["gcloud", "config", "get-value", "account"])
        assert _argv(mock_run) == ["C:/sdk/gcloud.cmd", "config", "get-value", "account"]

    def test_falls_back_to_bare_gcloud_name(self, mock_run):
        """Without a PATH match the bare name is still passed through."""
        with patch("gcp.gcp_setup.shutil.which", return_value=None):
            gs.run_command(["gcloud", "version"])
        assert _argv(mock_run) == ["gcloud", "version"]
        assert mock_run.call_args.kwargs["shell"] is False

    def test_non_gcloud_program_is_not_rewritten(self, mock_run):
        """Only a leading 'gcloud' is resolved; other programs are left alone."""
        gs.run_command(["python", "-V"])
        assert _argv(mock_run) == ["python", "-V"]
        assert mock_run.call_args.kwargs["shell"] is False

    @pytest.mark.parametrize(
        "value",
        [
            "Workspace Hub",
            'say "hi" and \'bye\'',
            "left;right",
            "first && second",
            "$(id)",
            "`whoami`",
            'all: "a b"; c && $(d) `e` f',
        ],
    )
    def test_metacharacter_value_is_one_unchanged_element(self, mock_run, value):
        """Values with spaces, quotes, ';', '&&', '$()' and backticks stay one element."""
        gs.run_command(["gcloud", "x", f"--name={value}", value])
        argv = _argv(mock_run)
        assert argv[-2:] == [f"--name={value}", value]
        assert len(argv) == 4
        assert mock_run.call_args.kwargs["shell"] is False

    @pytest.mark.parametrize(
        "value", ["BILL; rm -rf ~", "x && y", "$(id)", "`id`", "two words"]
    )
    def test_caller_passes_metacharacter_value_as_one_element(self, mock_run, value):
        """A caller (link_billing) hands an unusual billing value over intact."""
        gs.link_billing("proj-1", value)
        argv = _argv(mock_run)
        assert argv[-1] == f"--billing-account={value}"
        assert argv.count(f"--billing-account={value}") == 1
        assert mock_run.call_args.kwargs["shell"] is False


# ── Simple helpers ───────────────────────────────────────────────────────


class TestHelpers:
    """Project ID generation, gcloud detection and account lookup."""

    @pytest.mark.parametrize("project_id", ["a12345", "a" * 29 + "1", "valid-project-1"])
    def test_is_valid_project_id_accepts_boundaries(self, project_id):
        """Shortest, longest and hyphenated valid IDs are accepted."""
        assert gs.is_valid_project_id(project_id) is True

    @pytest.mark.parametrize(
        "project_id",
        ["a1234", "a" * 30 + "1", "Abcdef", "-abcde", "abcde-", "agoogle1", "assl123"],
    )
    def test_is_valid_project_id_rejects_invalid_boundaries(self, project_id):
        """Too short, too long, uppercase, edge hyphens and reserved words are refused."""
        assert gs.is_valid_project_id(project_id) is False

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
        assert _argv(mock_run) == [GCLOUD_PATH, "config", "get-value", "account"]

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
        assert cmd == [GCLOUD_PATH, "projects", "create", "proj-1", "--name=Workspace Automation Hub"]

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
        apis = {tok for tok in cmd if tok.endswith(".googleapis.com")}
        assert apis == {
            f"{name}.googleapis.com"
            for name in ("gmail", "calendar-json", "drive")
            + ("generativelanguage", "billingbudgets")
        }
        assert cmd[-1] == "--project=proj-1"
        assert cmd[:3] == [GCLOUD_PATH, "services", "enable"]
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
        assert "--display-name=Workspace Integration Budget" in cmd
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

    def _side_effect(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess:
        joined = " ".join(command)
        for key, value in responses.items():
            if key in joined:
                return value
        raise AssertionError(f"unexpected command: {joined}")

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
        assert not any("oauth-brands list" in " ".join(c) for c in cmds)

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
        assert not any(
            "oauth-clients" in " ".join(c[0][0]) for c in mock_run.call_args_list
        )

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
        main_env["run_command"].assert_called_once_with(
            ["gcloud", "auth", "login"], interactive=True
        )
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

    @pytest.mark.parametrize("bad", ["BILL; rm -rf ~", "0123 ABCD", "$(id)"])
    def test_invalid_billing_id_exits(self, main_env: dict[str, Any], bad: str) -> None:
        """Billing IDs with shell metacharacters are rejected before any gcloud call."""
        main_env["select_billing_account"].return_value = bad
        with pytest.raises(SystemExit):
            gs.main()
        main_env["create_project"].assert_not_called()

    @pytest.mark.parametrize(
        "bad",
        [
            "My-Proj",
            "abc",
            "proj-",
            "1project",
            "p; rm -rf ~",
            "a" * 31,
            "google1",
            "abcssl1",
        ],
    )
    def test_invalid_project_id_exits(self, main_env: dict[str, Any], bad: str) -> None:
        """Project IDs outside GCP's format are rejected before creation."""
        main_env["input"].return_value = bad
        with pytest.raises(SystemExit):
            gs.main()
        main_env["create_project"].assert_not_called()

    def test_project_creation_failure_exits(self, main_env):
        """Failed project creation exits before billing is linked."""
        main_env["create_project"].return_value = False
        with pytest.raises(SystemExit):
            gs.main()
        main_env["link_billing"].assert_not_called()


class TestShellFreeInvocation:
    """Every subprocess.run call made by gcp_setup is a shell-free argument list."""

    def test_every_subprocess_call_passes_shell_false(
        self, mock_run, tmp_path, monkeypatch, capsys
    ):
        """A representative full run (login, billing, APIs, OAuth) never uses a shell."""
        monkeypatch.setattr(gs, "__file__", str(tmp_path / "gcp" / "gcp_setup.py"))
        accounts = iter(["", "me@x.com"])  # no session first, so login runs

        def _respond(command, **_kwargs):
            joined = " ".join(command)
            if "config get-value account" in joined:
                return _completed(stdout=next(accounts))
            if "billing accounts list" in joined:
                return _completed(stdout=json.dumps(MENU_ENTRIES))
            if "oauth-brands create" in joined:
                return _completed(stdout=json.dumps({"name": "brands/1"}))
            if "oauth-clients create" in joined:
                return CLIENT_OK
            return _completed()

        mock_run.side_effect = _respond
        with patch("builtins.input", side_effect=["1", "my-proj-1"]):
            exit_error = None
            try:
                gs.main()
            except SystemExit as exc:  # reported below, after the call checks
                exit_error = exc

        calls = mock_run.call_args_list
        for call in calls:
            assert isinstance(call.args[0], list), call.args[0]
            assert call.kwargs["shell"] is False
        assert len(calls) >= 9
        assert exit_error is None
        assert "Setup complete" in capsys.readouterr().out
