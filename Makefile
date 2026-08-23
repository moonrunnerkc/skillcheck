.PHONY: lint test regen-golden regen-golden-warnings regen-self-host-fixtures verify-release

# Coverage floor for full-suite runs. Not in pyproject addopts, which would also
# apply it to single-file runs; see the comment there.
COV_FLOOR := 75

# Pre-1.0 sentinel version. Stale references to this string must not appear in
# shipped files; update only if a new major version creates a new legacy line.
LEGACY_VERSION := 0.2.0

# Current package version, read from pyproject.toml. Used to assert the README's
# pre-commit `rev:` example tracks the shipped version.
VERSION := $(shell grep -m1 '^version' pyproject.toml | sed 's/.*"\(.*\)".*/\1/')

regen-self-host-fixtures:
	python3 scripts/regen_self_host_fixtures.py

# Rewrite tests/fixtures/golden/ from the current renderers. Read the diff
# before committing: a golden that moves without a formatters.py change means
# something upstream shifted.
regen-golden:
	SKILLCHECK_REGEN_GOLDEN=1 python3 -m pytest tests/test_formatter_golden.py -q

# Rewrite tests/golden/*/expected.txt from the current rules. Same rule as
# above: read the diff, a golden that moves on its own is a regression.
regen-golden-warnings:
	SKILLCHECK_REGEN_GOLDEN=1 python3 -m pytest tests/test_golden_warnings.py -q

lint:
	ruff check src tests scripts
	mypy

test:
	python3 -m pytest tests/ --cov-fail-under=$(COV_FLOOR)

verify-release:
	ruff check src tests scripts
	mypy
	python3 -m pytest tests/ -v --cov-fail-under=$(COV_FLOOR)
	skillcheck --version
	skillcheck skills/skillcheck/SKILL.md
	skillcheck skills/skillcheck/SKILL.md --analyze-graph
	grep -rn "$(LEGACY_VERSION)" --include="*.py" --include="*.toml" --include="*.md" --include="*.yml" src/ pyproject.toml README.md action.yml && echo "FAIL: $(LEGACY_VERSION) references found" && exit 1 || echo "OK: no $(LEGACY_VERSION) references in release files"
	grep -rn "moonrunnerkc/skillcheck@v0" README.md && echo "FAIL: @v0 reference in README" && exit 1 || echo "OK: no @v0 in README"
	@grep -q "rev: v$(VERSION)" README.md && echo "OK: README pre-commit rev matches v$(VERSION)" || { echo "FAIL: README pre-commit 'rev:' does not match pyproject version v$(VERSION); update the rev in README.md"; exit 1; }
	@python3 -c "import build" 2>/dev/null && python3 -m build --sdist --wheel || echo "INFO: build module not available, skipping sdist/wheel check"
