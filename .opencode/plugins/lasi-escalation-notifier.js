import { readFile, readdir } from "node:fs/promises"
import { join, resolve } from "node:path"

export const LasiEscalationNotifier = async ({ client, directory }) => {
  // Detached coordinator processes load project plugins too. Only the user's
  // normal OpenCode process should present UI notifications.
  if (process.env.LASI_INTERNAL_COORDINATOR === "1") return {}

  const notificationDirectory = resolve(directory, ".lasi", "notifications")
  const shown = new Set()

  const show = async (path) => {
    if (shown.has(path)) return
    try {
      const payload = JSON.parse(await readFile(path, "utf8"))
      if (payload.type !== "lasi_escalation") return
      const text = [
        `LASI needs feedback for project ${payload.project_id}.`,
        `Question: ${payload.question}`,
        `Reply: ${payload.feedback_command}`,
      ].join("\n")
      await client.tui.showToast({
        body: {
          title: "LASI needs feedback",
          message: `${payload.question} — use /lasi-feedback`,
          variant: "warning",
          duration: 15000,
        },
      })
      await client.tui.appendPrompt({ body: { text } })
      shown.add(path)
    } catch (error) {
      // Atomic writes and unlink events can race with the watcher. A later
      // change or OpenCode restart will retry any still-pending notification.
    }
  }

  try {
    for (const name of await readdir(notificationDirectory)) {
      if (name.endsWith(".json")) await show(join(notificationDirectory, name))
    }
  } catch (error) {
    // The directory is created lazily by the first escalation.
  }

  return {
    event: async ({ event }) => {
      if (event.type !== "file.watcher.updated") return
      if (event.properties.event === "unlink") return
      const path = resolve(directory, event.properties.file)
      if (!path.startsWith(`${notificationDirectory}/`) || !path.endsWith(".json")) return
      await show(path)
    },
  }
}
