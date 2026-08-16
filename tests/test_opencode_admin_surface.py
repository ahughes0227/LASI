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
    "lasi-build-capability.md",
    "lasi-build-workflow.md",
    "lasi-build-component.md",
}


def test_only_governed_commands_are_user_facing() -> None:
    command_dir = ROOT / ".opencode" / "command"
    command_files = {path.name for path in command_dir.glob("*.md")}

    assert command_files == COMMANDS
    for name in command_files - {
        "lasi-build-capability.md",
        "lasi-build-workflow.md",
        "lasi-build-component.md",
    }:
        assert "agent: lasi-admin" in (command_dir / name).read_text()
    assert (
        "agent: lasi-capability-builder" in (command_dir / "lasi-build-capability.md").read_text()
    )
    assert "agent: lasi-workflow-builder" in (command_dir / "lasi-build-workflow.md").read_text()


def test_admin_is_primary_and_coordinator_is_internal() -> None:
    config = (ROOT / "opencode.json").read_text()
    admin = (ROOT / ".opencode" / "agent" / "lasi-admin.md").read_text()
    coordinator = (ROOT / ".opencode" / "agent" / "lasi-coordinator.md").read_text()

    assert '"default_agent": "lasi-admin"' in config
    assert "mode: primary" in admin
    assert "mode: subagent" in coordinator
    assert "AgentResult" in coordinator
    assert "TaskGraphProposal" in coordinator


def test_capability_builder_is_a_bounded_primary_command_agent() -> None:
    config = (ROOT / "opencode.json").read_text()
    builder = (ROOT / ".opencode" / "agent" / "lasi-capability-builder.md").read_text()
    command = (ROOT / ".opencode" / "command" / "lasi-build-capability.md").read_text()

    assert '"lasi-capability-builder"' in config
    assert "mode: primary" in builder
    assert "CapabilityRegistrationProposal" in builder
    assert "update_toolbox" in command
    assert "REUSE" in command and "COMPOSE" in command


def test_workflow_builder_is_a_bounded_primary_command_agent() -> None:
    config = (ROOT / "opencode.json").read_text()
    builder = (ROOT / ".opencode" / "agent" / "lasi-workflow-builder.md").read_text()
    command = (ROOT / ".opencode" / "command" / "lasi-build-workflow.md").read_text()

    assert '"lasi-workflow-builder"' in config
    assert "mode: primary" in builder
    assert "WorkflowRegistrationProposal" in builder
    assert "WorkflowBuildPlan" in command
    assert "REUSE" in command and "COMPOSE" in command


def test_component_builder_is_a_bounded_primary_command_agent() -> None:
    config = (ROOT / "opencode.json").read_text()
    builder = (ROOT / ".opencode" / "agent" / "lasi-component-builder.md").read_text()
    command = (ROOT / ".opencode" / "command" / "lasi-build-component.md").read_text()

    assert '"lasi-component-builder"' in config
    assert "mode: primary" in builder
    assert "ComponentRegistrationProposal" in builder
    assert "update_toolbox" in command
    assert "REUSE" in command and "COMPOSE" in command


def test_escalations_have_an_opencode_ui_bridge() -> None:
    plugin = ROOT / ".opencode" / "plugins" / "lasi-escalation-notifier.js"
    content = plugin.read_text()

    assert "file.watcher.updated" in content
    assert "client.tui.showToast" in content
    assert "client.tui.appendPrompt" in content
    assert "/lasi-feedback" in content or "feedback_command" in content
