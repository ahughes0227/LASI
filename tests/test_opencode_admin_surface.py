from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {
    "lasi-start.md",
    "lasi-status.md",
    "lasi-pause.md",
    "lasi-resume.md",
    "lasi-cancel.md",
    "lasi-feedback.md",
    "lasi-report.md",
}


def test_only_admin_commands_are_user_facing() -> None:
    command_dir = ROOT / ".opencode" / "command"
    command_files = {path.name for path in command_dir.glob("*.md")}

    assert command_files == COMMANDS
    for name in command_files:
        assert "agent: lasi-admin" in (command_dir / name).read_text()


def test_admin_is_primary_and_coordinator_is_internal() -> None:
    config = (ROOT / "opencode.json").read_text()
    admin = (ROOT / ".opencode" / "agent" / "lasi-admin.md").read_text()
    coordinator = (ROOT / ".opencode" / "agent" / "lasi-coordinator.md").read_text()

    assert '"default_agent": "lasi-admin"' in config
    assert "mode: primary" in admin
    assert "mode: subagent" in coordinator
    assert "CoordinatorDirective" in coordinator


def test_escalations_have_an_opencode_ui_bridge() -> None:
    plugin = ROOT / ".opencode" / "plugins" / "lasi-escalation-notifier.js"
    content = plugin.read_text()

    assert "file.watcher.updated" in content
    assert "client.tui.showToast" in content
    assert "client.tui.appendPrompt" in content
    assert "/lasi-feedback" in content or "feedback_command" in content
