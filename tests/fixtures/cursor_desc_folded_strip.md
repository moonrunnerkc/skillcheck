---
name: cursor-folded-strip
description: >-
  Validates SKILL.md files for Cursor compatibility. Use when checking
  that folded-strip (>-) descriptions render correctly in Cursor's UI.
---

# Body

This SKILL.md uses `description: >-` (folded strip). PyYAML and Cursor
both render the description correctly. This fixture must not trigger
the cursor-description-block-scalar rule.
