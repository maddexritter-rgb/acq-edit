---
name: alex
description: >
  Shortcut /alex: independently check the current or supplied piece of content against
  the shared creator content framework. Routes to audit-script quick-check mode for a
  concise verdict and specific fixes. Accepts posts, carousels, scripts, videos and cuts.
---

# /alex

This is a command alias, not another review rubric.

→ Use skill: `audit-script`, **Quick check**, at `__ACQ_SKILLS__/audit-script/SKILL.md`. Resolve `~` to the current user's home directory and read that exact canonical file, including in Claude Code; do not substitute a stale copy from another skill root.

Pass through the content/path/link or instructions following the command. With no arguments, use the clearly identified piece just made in this session; if none is available or the target is ambiguous, ask which piece. Follow the owning skill's fresh-reviewer requirement and compact verdict/fixes format. This invokes a review, not editing or publishing.

Claude Code invocation: `/alex [content or request]`. Codex explicit skill mention: `$alex [content or request]`; also recognize a user message beginning `/alex` as this shortcut when the host passes it through as text.
