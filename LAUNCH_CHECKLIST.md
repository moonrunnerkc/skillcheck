# Launch Checklist: skillcheck v1.0.0

Steps for the maintainer to run after the Phase 3D agent commit. Each step is sequenced for safety. Do not skip or reorder.

1. **Review Phase 3D artifacts.** Read `RELEASE_NOTES_v1.0.0.md`, `LAUNCH_POST_v1.0.md`, and `LAUNCH_CHECKLIST.md` (this file). Verify `dist/skillcheck-1.0.0.tar.gz` and `dist/skillcheck-1.0.0-py3-none-any.whl` exist locally. Edit any of these files in place if needed before pushing.

2. **Push the release-prep branch.**
   ```bash
   git push origin v1-phase3d-release-prep
   ```

3. **Open and merge the PR.** Open a PR from `v1-phase3d-release-prep` to `main`. Confirm CI is green. Merge.

4. **Pull main locally.**
   ```bash
   git checkout main && git pull origin main
   ```

5. **Verify the local tags point at the merged commit.** Check `git log --oneline -3` to confirm the HEAD SHA. If main was rebased or had additional commits merged after the tags were created, delete and re-create them:
   ```bash
   git tag -d v1.0.0 v1
   git tag -a v1.0.0 -m "skillcheck 1.0.0
   See CHANGELOG.md for the complete list of changes.
   Highlights:

   Agent-native semantic critique via --emit-critique-prompt and --ingest-critique
   Capability graph extraction (heuristic and agent-mode)
   Validation history ledger via --history and --show-history
   Vendor-tuned prompt templates (claude, codex, cursor) for critique and graph modes
   New rule namespaces: semantic., graph., history.*
   Self-hosted SKILL.md at skills/skillcheck/SKILL.md"
   git tag v1 v1.0.0
   ```

6. **Push the tags.**
   ```bash
   git push origin v1.0.0 v1
   ```
   This is the point of no return for the release tag. Confirm the merged commit is correct before running this.

7. **Upload to PyPI.** PyPI credentials required.
   ```bash
   python3 -m twine upload dist/*
   ```
   If the local `dist/` was cleaned since the Phase 3D build, rebuild first: `rm -rf dist/ && python3 -m build --sdist --wheel && python3 -m twine check dist/*`.

8. **Create the GitHub Release.** Navigate to https://github.com/moonrunnerkc/skillcheck/releases/new. Select the `v1.0.0` tag. Paste the full contents of `RELEASE_NOTES_v1.0.0.md` into the description field. Mark as latest release. Publish.

9. **Verify the install from a clean environment.**
   ```bash
   pip install skillcheck==1.0.0 && skillcheck --version
   ```
   Expected output: `skillcheck 1.0.0`.

10. **Publish the launch post.** The single canonical version is `LAUNCH_POST_v1.0.md`. Per-platform adaptations (X threading, dev.to canonical URL, LinkedIn formatting, r/ClaudeAI markdown) are the maintainer's call. Target platforms per plan section 8: X (@KChackerman), dev.to, LinkedIn, r/ClaudeAI.

11. **Submit to awesome-lists.** Each is a separate PR or issue per their contribution guidelines. Lists from plan section 8:
    - VoltAgent awesome-agent-skills list
    - skillmatic-ai list
    - heilcheng/awesome-agent-skills

12. **Engage on agentskills.io community channels** per plan section 8.

13. **7-day post-launch check.** From a clean environment:
    ```bash
    pip download skillcheck==1.0.0
    ```
    Confirm the wheel and sdist download cleanly from PyPI. Check the GitHub release page download counts as an adoption signal.
