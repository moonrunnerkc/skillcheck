---
name: cursor-literal
description: |
  Generates a description that PyYAML accepts but Cursor's UI parser
  silently drops, leaving the skill panel empty. Use when reproducing
  the issue #1 literal block scalar case.
---

# Body

This SKILL.md uses `description: |` (literal). PyYAML accepts it,
but Cursor's skills UI renders the description as empty.
