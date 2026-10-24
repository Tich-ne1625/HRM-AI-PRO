"""Binary-safe backup, full-table fingerprints and restore into a separate empty namespace."""

import argparse
import json
import secrets

from common import OUT, Target
from deploy import deploy

PROGRAM = """
import hashlib,json
from sqlalchemy import create_engine,select,text
from app.core.config import Settings
from app.core.database import Base
import app.models
s=Settings(_env_file=None)
engine=create_engine(s.database_url.get_secret_value())
tables={}
with engine.connect() as c:
    c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
    head=c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    for table in Base.metadata.sorted_tables:
        rows=sorted(json.dumps(dict(r),sort_keys=True,default=str,separators=(',',':')) for r in c.execute(select(table)).mappings())
        tables[table.name]={'count':len(rows),'sha256':hashlib.sha256('\\n'.join(rows).encode()).hexdigest()}
print(json.dumps({'head':head,'tables':tables},sort_keys=True))
engine.dispose()
"""


def fingerprint(t):
    return json.loads(t.exec("python", "-", body=PROGRAM))


def backup(t):
    data = t.exec(
        "pg_dump",
        "-U",
        "insighthr",
        "-d",
        "phase10_acceptance_test",
        "-Fc",
        binary=True,
        workload="statefulset/postgres",
    )
    assert data.startswith(b"PGDMP"), "Expected PostgreSQL custom archive"
    path = OUT / "backups" / f"{secrets.token_hex(8)}.dump"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)
    return path


def restore(source, release):
    password = secrets.token_urlsafe(24)
    email = "restore-" + secrets.token_hex(4) + "@example.com"
    source.exec(
        "python",
        "-m",
        "app.cli.create_admin",
        "--email",
        email,
        "--password-stdin",
        body=password + "\n" + password + "\n",
    )
    login_program = """
import json,urllib.request,http.cookiejar
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
request=urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/login',data=json.dumps(CREDENTIALS).encode(),headers={'Origin':'http://localhost:13010','Content-Type':'application/json'})
with opener.open(request) as response: user=json.load(response)
print(json.dumps({'user':user['id'],'cookies':'; '.join(c.name+'='+c.value for c in jar)}))
""".replace("CREDENTIALS", repr({"email": email, "password": password}))
    session = json.loads(source.exec("python", "-", body=login_program))
    before = fingerprint(source)
    archive = backup(source)
    target = Target("insighthr-phase10-restore")
    # Refuse to overwrite any pre-existing namespace, even an earlier test restore.
    assert not any(
        n["metadata"]["name"] == target.namespace
        for n in target.json("get", "namespaces")["items"]
    ), "Restore requires a new namespace"
    deploy(target, "local-http", release, db_only=True)
    # Preserve signing key so existing token families remain meaningful after restore.
    auth = source.json("get", "secret", "authentication")
    target.apply(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "authentication"},
            "type": "Opaque",
            "data": auth["data"],
        }
    )
    target.exec(
        "pg_restore",
        "-U",
        "insighthr",
        "-d",
        "phase10_acceptance_test",
        "--exit-on-error",
        "--no-owner",
        body=archive.read_bytes(),
        binary=True,
        workload="statefulset/postgres",
    )
    # Do not publish a second ingress with the same host while the source stays running.
    deploy(target, "local-http", release)
    after = fingerprint(target)
    assert before == after, "Restored data changed"
    verify_program = """
import json,urllib.request
request=urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/me',headers={'Cookie':COOKIES})
with urllib.request.urlopen(request) as response: user=json.load(response)
assert user['id']==EXPECTED
print('restored session valid')
""".replace("COOKIES", repr(session["cookies"])).replace(
        "EXPECTED", repr(session["user"])
    )
    assert (
        target.exec("python", "-", body=verify_program).strip()
        == "restored session valid"
    )
    source.report(
        "restore.json",
        {
            "status": "passed",
            "source": source.namespace,
            "target": target.namespace,
            "archive_bytes": archive.stat().st_size,
            "scope": "all ORM columns/tables including sessions, audit, limiter; no records exported",
            "fingerprint": before,
        },
    )
    print("Restore verified in a separate namespace; source unchanged.", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["fingerprint", "backup", "restore-test"])
    p.add_argument("--release")
    a = p.parse_args()
    t = Target()
    if a.action == "fingerprint":
        print(json.dumps(fingerprint(t)))
    elif a.action == "backup":
        print("Backup saved outside Git:", backup(t).name)
    else:
        if not a.release:
            raise ValueError("--release required")
        restore(t, a.release)


if __name__ == "__main__":
    main()
