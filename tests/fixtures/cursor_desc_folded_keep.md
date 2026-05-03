---
name: cursor-folded-keep
description: >
  Generates a description that PyYAML accepts but Cursor's UI parser
  silently drops, leaving the skill panel empty. Use when reproducing
  the issue #1 folded-keep case.
---

# Body

This SKILL.md uses `description: >` (folded keep). PyYAML accepts it,
but Cursor's skills UI renders the description as empty.
