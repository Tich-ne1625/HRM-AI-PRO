"""Read and fingerprint the exact Phase 6 smoke fixture, including immutable history.

Run before restart and again with only PostgreSQL started, before migration reruns.
Only the fingerprint is printed; private snapshots and user data stay in memory.
"""

import argparse
import hashlib
import json
import subprocess

SQL = """
SELECT jsonb_build_object(
  'head', (SELECT version_num FROM alembic_version),
  'users', (SELECT count(*) FROM users),
  'employees', (SELECT count(*) FROM employees),
  'cycles', (SELECT jsonb_agg(to_jsonb(c) ORDER BY c.id) FROM review_cycles c),
  'participants', (SELECT jsonb_agg(to_jsonb(p) ORDER BY p.id) FROM cycle_participants p),
  'kpis', (SELECT jsonb_agg(to_jsonb(k) ORDER BY k.id) FROM employee_kpis k),
  'assignments', (SELECT jsonb_agg(to_jsonb(a) ORDER BY a.id) FROM feedback_assignments a),
  'feedback', (SELECT jsonb_agg(to_jsonb(f) ORDER BY f.id) FROM feedback f),
  'analyses', (SELECT jsonb_agg(to_jsonb(a) ORDER BY a.id) FROM ai_analyses a),
  'reviews', (SELECT jsonb_agg(to_jsonb(r) ORDER BY r.id) FROM performance_reviews r),
  'revisions', (SELECT jsonb_agg(to_jsonb(v) ORDER BY v.calculation_version)
                FROM performance_review_revisions v)
);
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-project", required=True)
    args = parser.parse_args()
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            args.compose_project,
            "--env-file",
            ".env.example",
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "$1"',
            "sh",
            SQL,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    data = json.loads(result.stdout)
    assert data["head"] == "20261024_0008"
    analyses = data["analyses"] or []
    assert len(analyses) == 4, "Seed the explicit offline AI acceptance fixture first"
    assert sorted(a["status"] for a in analyses) == ["FAILED", "RUNNING", "SUCCEEDED", "SUCCEEDED"]
    assert sorted(a["audience"] for a in analyses) == ["HR_PRIVATE", "HR_PRIVATE", "PUBLIC", "PUBLIC"]
    assert all(a["model"] == "demo-fixture" for a in analyses)
    assert all((a["output"] is not None) == (a["status"] == "SUCCEEDED") for a in analyses)
    assert all(a["calculation_version"] == 2 for a in analyses)
    assert data["users"] >= 7 and data["employees"] >= 7
    assert len(data["cycles"]) == 2 and sorted(c["status"] for c in data["cycles"]) == [
        "ACTIVE",
        "CLOSED",
    ]
    assert len(data["participants"]) == 2 and len(data["kpis"]) == 1
    assert data["kpis"][0]["actual"] == 90
    assert len(data["assignments"]) == 7
    assert sorted(a["status"] for a in data["assignments"]).count("OPEN") == 1
    assert sorted(a["status"] for a in data["assignments"]).count("CANCELLED") == 1
    assert (
        len(data["feedback"]) == 5 and sum(f["rating"] for f in data["feedback"]) == 20
    )
    assert len(data["reviews"]) == 1 and len(data["revisions"]) == 2
    review = data["reviews"][0]
    participant = next(
        p for p in data["participants"] if p["id"] == review["participant_id"]
    )
    assert review["final_score"] == 87 and review["calculation_version"] == 2
    assert (
        review["finalized_at"] and review["finalized_at"] == participant["finalized_at"]
    )
    assert review["evidence_version"] == participant["evidence_version"]
    assert [v["final_score"] for v in data["revisions"]] == [24, 87]
    assert data["revisions"][1]["evidence_hash"] == review["evidence_hash"]
    print(
        hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


if __name__ == "__main__":
    main()
