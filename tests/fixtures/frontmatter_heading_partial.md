---
## name: my-skill
description: Validates SKILL.md files. Use when checking only the name field is supplied as a markdown heading.
---

# Body

This SKILL.md uses `## name:` as a markdown heading but provides
description as a real YAML key. Only the name.required diagnostic should
carry the markdown-heading hint.
