"""Roundtrip upgrade and PostgreSQL-only restart on the isolated UI test project.

Hashes all columns of every pre-Phase-9 table; artifacts contain counts/digests only.
Does not accept arbitrary project/database arguments and never resets a volume.
"""

import json
import subprocess
import time

from phase9_browser import COMPOSE, ROOT

FINGERPRINT = """
import hashlib, json
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from app.core.config import Settings
from app.core.database import Base
import app.models
s=Settings(_env_file=None)
assert s.app_env=='test'
assert make_url(s.database_url.get_secret_value()).database=='phase9_ui_test'
engine=create_engine(s.database_url.get_secret_value())
tables={}
with engine.connect() as c:
    head=c.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one()
    for t in Base.metadata.sorted_tables:
        if t.name=='auth_login_limits': continue
        rows=sorted(json.dumps(dict(r),sort_keys=True,default=str,separators=(',',':')) for r in c.execute(select(t)).mappings())
        tables[t.name]={'count':len(rows),'sha256':hashlib.sha256('\\n'.join(rows).encode()).hexdigest()}
print(json.dumps({'head':head,'tables':tables},sort_keys=True))
engine.dispose()
"""


def run(args, body=None):
    result = subprocess.run(
        COMPOSE + args, cwd=ROOT, input=body, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, "Isolated persistence operation failed: " + " ".join(
        args[:5]
    )
    return result.stdout


def snapshot():
    return json.loads(run(["exec", "-T", "api", "python", "-"], FINGERPRINT))


def main():
    before = snapshot()
    assert before["head"] == "20261024_0008"
    assert before["tables"]["performance_review_revisions"]["count"] >= 2
    assert before["tables"]["ai_analyses"]["count"] == 3
    run(["exec", "-T", "api", "alembic", "downgrade", "20261022_0007"])
    old = snapshot()
    assert old["head"] == "20261022_0007" and old["tables"] == before["tables"]
    run(["exec", "-T", "api", "alembic", "upgrade", "head"])
    assert snapshot() == before
    run(["restart", "postgres"])
    for _ in range(60):
        try:
            after = snapshot()
            break
        except AssertionError:
            time.sleep(0.5)
    else:
        raise RuntimeError("PostgreSQL did not become ready")
    # Read occurs before any migrate container can be run again.
    assert after == before
    report = {
        "status": "passed",
        "head": before["head"],
        "roundtrip_0007_0008": True,
        "postgres_only_restart_read_before_migration": True,
        "scope": "all columns of all pre-Phase-9 ORM tables; auth_login_limits excluded",
        "tables": before["tables"],
    }
    out = ROOT / ".superpowers/sdd/phase-9/persistence.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "tables"}), flush=True)


if __name__ == "__main__":
    main()
