.PHONY: regen-self-host-fixtures verify-release

regen-self-host-fixtures:
	python3 scripts/regen_self_host_fixtures.py

verify-release:
	python3 -m pytest tests/ -v
	skillcheck --version
	skillcheck skills/skillcheck/SKILL.md
	skillcheck skills/skillcheck/SKILL.md --analyze-graph
	grep -rn "0\.2\.0" --include="*.py" --include="*.toml" --include="*.md" --include="*.yml" src/ pyproject.toml README.md action.yml && echo "FAIL: 0.2.0 references found" && exit 1 || echo "OK: no 0.2.0 references in release files"
	grep -rn "moonrunnerkc/skillcheck@v0" README.md && echo "FAIL: @v0 reference in README" && exit 1 || echo "OK: no @v0 in README"
	@command -v python3 -c "import build" 2>/dev/null && python3 -m build --sdist --wheel || echo "INFO: build module not available, skipping sdist/wheel check"
