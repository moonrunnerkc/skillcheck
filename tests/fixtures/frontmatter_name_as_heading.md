---
## name: my-skill
## description: Validates SKILL.md files using markdown headings instead of YAML keys.
---

# Body

This SKILL.md mistakes YAML frontmatter for markdown and uses `## name:`
and `## description:` as if they were headings. Both keys end up missing
from the parsed frontmatter.
