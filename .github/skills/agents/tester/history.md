# Tester Error History

<!-- Append new entries at the top -->

---
## 2026-04-28 - Tester could not execute terminal commands
**Error:** Tester appeared to have "no functionality" because subagent runs reported missing terminal/shell capability, so dry-run commands never executed.
**Fix:** Updated `tools` in `.github/agents/tester.agent.md` to alias mode (`read`, `search`, `execute`, `web`) and corrected venv path to `../.venv/bin/activate`.
**Lesson:** For custom agents, prefer supported tool aliases over raw function names; add a tool preflight check before running test commands.
