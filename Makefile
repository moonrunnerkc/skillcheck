.PHONY: regen-self-host-fixtures verify-release

# Pre-1.0 sentinel version. Stale references to this string must not appear in
# shipped files; update only if a new major version creates a new legacy line.
LEGACY_VERSION := 0.2.0

regen-self-host-fixtures:
	python3 scripts/regen_self_host_fixtures.py

verify-release:
	python3 -m pytest tests/ -v
	skillcheck --version
	skillcheck skills/skillcheck/SKILL.md
	skillcheck skills/skillcheck/SKILL.md --analyze-graph
	grep -rn "$(LEGACY_VERSION)" --include="*.py" --include="*.toml" --include="*.md" --include="*.yml" src/ pyproject.toml README.md action.yml && echo "FAIL: $(LEGACY_VERSION) references found" && exit 1 || echo "OK: no $(LEGACY_VERSION) references in release files"
	grep -rn "moonrunnerkc/skillcheck@v0" README.md && echo "FAIL: @v0 reference in README" && exit 1 || echo "OK: no @v0 in README"
	@command -v python3 -c "import build" 2>/dev/null && python3 -m build --sdist --wheel || echo "INFO: build module not available, skipping sdist/wheel check"
