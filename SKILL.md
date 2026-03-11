---
name: git-commit-crafter
description: Generates conventional commit messages from staged diffs, enforcing semantic versioning conventions and team-defined scopes.
version: "1.0.0"
author: brad
tags:
  - git
  - commits
  - devops
allowed-tools:
  - Bash
user-invocable: true
---

# git-commit-crafter

Generates conventional commit messages from staged git diffs. Reads the diff, infers the change type and scope, and produces a formatted commit message ready to paste or pipe directly into `git commit`.

## Trigger

Invoke when the user has staged changes and needs a commit message:

```
/git-commit-crafter
```

## Behavior

1. Run `git diff --cached` to read the staged changes.
2. Identify the change type from the diff: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, or `perf`.
3. Infer the scope from the files touched (e.g., `auth`, `api`, `cli`, `db`).
4. Write a subject line under 72 characters in the form `type(scope): imperative summary`.
5. If the diff spans more than one logical concern, add a short body paragraph per concern.
6. If any file path contains `BREAKING` or the diff removes a public API surface, append `BREAKING CHANGE:` footer.

## Output format

```
feat(auth): add OAuth2 PKCE flow for CLI clients

Replaces the implicit grant with PKCE to comply with RFC 9700.
Adds a local redirect server on a random port for the callback.

Closes #418
```

## Constraints

- Never invent change details not present in the diff.
- Do not reference internal ticket numbers unless they appear in branch name or diff.
- Keep the subject line imperative mood: "add", "fix", "remove", not "added" or "fixes".
- If the diff is empty, output: `No staged changes found. Run git add first.`

## Scope inference rules

| File path pattern      | Scope      |
|------------------------|------------|
| `src/auth/**`          | `auth`     |
| `src/api/**`           | `api`      |
| `src/cli/**`           | `cli`      |
| `src/db/**`            | `db`       |
| `tests/**`             | `test`     |
| `docs/**`              | `docs`     |
| `*.toml`, `*.cfg`      | `config`   |
| Mixed or root-level    | (omit scope) |
