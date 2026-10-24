"""Run existing PostgreSQL race/fault suites sequentially five times, recording actual counts."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def main():
    from sqlalchemy.engine import make_url

    if not (make_url(os.environ["TEST_DATABASE_URL"]).database or "").endswith("_test"):
        raise SystemExit("A disposable _test database is required")
    root = Path(__file__).resolve().parents[1]
    out = root / ".superpowers/sdd/phase-9/races"
    out.mkdir(parents=True, exist_ok=True)
    files = [
        "test_auth_refresh.py",
        "test_auth_mutations.py",
        "test_last_admin_concurrency.py",
        "test_organization_concurrency.py",
        "test_cycle_concurrency.py",
        "test_kpi_concurrency.py",
        "test_feedback_concurrency.py",
        "test_performance_concurrency.py",
        "test_ai_workflows.py",
        "test_login_limits.py",
    ]
    results = []
    for number in range(1, 6):
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                *["tests/integration/" + name for name in files],
            ],
            cwd=root / "apps/api",
            text=True,
            capture_output=True,
            check=False,
        )
        (out / f"round-{number}.log").write_text(
            run.stdout + run.stderr, encoding="utf-8"
        )
        passed = re.search(r"(\d+) passed", run.stdout)
        result = {
            "round": number,
            "returncode": run.returncode,
            "passed": int(passed.group(1)) if passed else 0,
        }
        results.append(result)
        (out / "report.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        print(json.dumps(result), flush=True)
        if run.returncode:
            return run.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
