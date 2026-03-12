# Case Study: The Skill That Silently Disappeared in VS Code

**A deploy skill worked in Claude Code but never loaded in VS Code/Copilot. No error. No warning. It just wasn't there.**

## The Setup

A team builds a deployment skill for their staging environment. The directory structure looks normal:

```
.github/skills/
└── deploy/
    └── SKILL.md
```

The `SKILL.md` is well-written:

```yaml
---
name: deploy-staging
description: Deploys the current branch to the staging environment. Use when the user asks to deploy, push to staging, or test in a staging environment.
allowed-tools: Bash(git:*) Bash(ssh:*) Bash(rsync:*)
---

# Deploy to Staging

## When to use
Activate when the user mentions deploying, staging, or wants to test their
changes in a pre-production environment.

## Steps
1. Verify the current branch is clean (no uncommitted changes)
2. Run the test suite: `scripts/run-tests.sh`
3. Build the project: `scripts/build.sh`
4. Deploy to staging: `scripts/deploy-staging.sh`
5. Report the staging URL and deployment status
```

The description scores 90/100 on quality. The frontmatter is valid YAML. The instructions are clear. Everything looks correct.

## The Problem

The skill loads fine in Claude Code. A teammate opens VS Code, types `/deploy-staging`, and... nothing. The skill doesn't appear in the slash command menu. It doesn't activate when a user asks to deploy. There is **no error message anywhere**.

The skill is invisible.

## Why It Happens

The [agentskills.io specification](https://agentskills.io/specification) requires that the `name` field "must match the parent directory name." The [VS Code Agent Skills documentation](https://code.visualstudio.com/docs/copilot/customization/agent-skills) makes the consequence explicit:

> **Important:** The `name` field in the `SKILL.md` frontmatter must match the parent directory name. For example, if the directory is `skills/my-skill/`, the `name` field must be `my-skill`. **If the name does not match, the skill is not loaded.**
>
> -- [VS Code docs: Contribute skills from extensions](https://code.visualstudio.com/docs/copilot/customization/agent-skills)

The directory is `deploy/`. The name is `deploy-staging`. They don't match. VS Code drops the skill silently.

This is by design. VS Code uses the directory name as the canonical identifier. When the frontmatter name doesn't match, the skill metadata is inconsistent, so VS Code refuses to load it rather than guess which name is correct. The problem is that it refuses *quietly*. No log entry, no diagnostic, no hint that something is wrong.

Claude Code doesn't enforce this constraint. The skill loads and works. So the author tests it in their primary environment, ships it, and never knows it's broken for half their team.

## How skillcheck Catches It

Running `skillcheck` against the mismatched file:

```
$ skillcheck deploy/SKILL.md
✗ FAIL  deploy/SKILL.md
    line 2  ✗ error  frontmatter.name.directory-mismatch  Name 'deploy-staging' does not
                     match parent directory 'deploy'. VS Code requires these to match or
                     the skill will not load.
                     name: deploy-staging | directory: deploy
            · info   compat.vscode-dirname  VS Code requires the name field ('deploy-staging')
                     to match the parent directory ('deploy'). This skill would not load
                     in VS Code/Copilot.

Checked 1 file: 0 passed, 1 failed
```

Two rules fire:

1. **`frontmatter.name.directory-mismatch`** (ERROR): the structural validation that catches the spec violation.
2. **`compat.vscode-dirname`** (INFO): the cross-agent compatibility warning that explains *why* it matters.

Exit code 1. The skill fails validation before it ever reaches VS Code.

## The Fix

Either rename the directory to match the name:

```
.github/skills/
└── deploy-staging/        # ← renamed from deploy/
    └── SKILL.md           # name: deploy-staging ✓
```

Or rename the skill to match the directory:

```yaml
name: deploy              # ← changed from deploy-staging
```

After fixing:

```
$ skillcheck deploy-staging/SKILL.md
✔ PASS  deploy-staging/SKILL.md
            · info  description.quality-score  Description quality score: 90/100.

Checked 1 file: 1 passed, 0 failed
```

## How This Happens in Practice

This isn't a contrived example. The mismatch happens naturally in these scenarios:

- **Renaming a skill** but only updating the frontmatter (or only renaming the directory).
- **Copying a skill** from one directory to another as a starting point and forgetting to update the name.
- **Using a shorter directory name** because `deploy/` feels cleaner than `deploy-staging/`, not realizing the name must match exactly.
- **CI temp paths** where the skill gets checked out into a directory with a different name than the original repo.

In every case, the failure mode is identical: it works in Claude Code, silently vanishes in VS Code, and nobody gets an error.

## Adding It to CI

The fix isn't just running `skillcheck` once. It's adding it to CI so this class of bug can never ship:

```yaml
# .github/workflows/skills.yml
- name: Validate SKILL.md files
  run: |
    pip install skillcheck
    skillcheck .github/skills/ --quiet
```

`--quiet` suppresses output and uses only the exit code. The pipeline fails if any skill has errors. The team deploys with confidence that every skill works across every agent.

## Why No Other Tool Catches This

The [agentskills.io reference library](https://github.com/agentskills/agentskills/tree/main/skills-ref) (`skills-ref`) validates frontmatter fields (name length, character constraints, required fields) but it is a parsing library, not a CLI linter. It does not check whether the name matches the parent directory because that's a filesystem concern outside its scope.

Claude Code's built-in validation doesn't check it because Claude Code doesn't require it. The constraint is a VS Code requirement derived from the spec, and Claude Code doesn't enforce VS Code's loading rules.

`skillcheck` is the only tool that validates a SKILL.md will work across agents *before you ship it*. That's the gap this exists to fill.

---

**Sources:**
- [agentskills.io Specification: `name` field requirements](https://agentskills.io/specification): "Must match the parent directory name"
- [VS Code Docs: Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills): "If the name does not match, the skill is not loaded"
- [VS Code Docs: Required folder structure](https://code.visualstudio.com/docs/copilot/customization/agent-skills): "Directory name must match the `name` field in SKILL.md"
