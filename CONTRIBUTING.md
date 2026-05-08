# Contributing

## Releasing

Every release pushes two tags pointing to the same commit:

1. An immutable patch tag (e.g., `v1.2.3`).
2. A force-updated `v1` moving major tag pointing to the same commit.

Steps:

```bash
# Bump version in pyproject.toml, commit, push to main.
git push origin main
git tag v1.2.3
git push origin v1.2.3
git tag -f v1
git push origin v1 --force
gh release create v1.2.3 --title "v1.2.3" --notes-file CHANGELOG_ENTRY.md
```

The `v1` tag always tracks the latest patch in the v1.x line. This lets GitHub Action users pin `@v1` for automatic updates or `@v1.2.3` for an immutable pin.