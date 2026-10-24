"""Exercise a disposable Compose stack through the web's same-origin API proxy.

Passwords are generated in memory and delivered to bootstrap only through stdin.
Run from repository root; the selected project must already be up and healthy.
"""

import argparse
import json
import secrets
import subprocess
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4


class Browser:
    def __init__(self, base: str, origin: str) -> None:
        self.base = base.rstrip("/")
        self.origin = origin
        self.jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, object] | None = None,
        expected: int = 200,
        csrf: bool = True,
    ) -> dict:
        headers = {"Origin": self.origin, "Content-Type": "application/json"}
        if csrf:
            for cookie in self.jar:
                if cookie.name == "insighthr_csrf":
                    headers["X-CSRF-Token"] = cookie.value
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            if response.status != expected:
                raise RuntimeError(
                    f"Unexpected status for {method} {path}: {response.status}"
                )
            raw = response.read()
            return json.loads(raw) if raw else {}


def organization_smoke(admin: Browser, hr: Browser, suffix: str) -> None:
    if hr.request("/api/v1/review-cycles?status=ACTIVE")["total"]:
        raise RuntimeError(
            "Phase 4 smoke requires a fresh disposable project without an ACTIVE cycle"
        )
    password = secrets.token_urlsafe(24)
    accounts = {}
    browsers = {}
    for name, role in (
        ("manager", "MANAGER"),
        ("employee", "EMPLOYEE"),
        ("peer", "EMPLOYEE"),
        ("subordinate", "EMPLOYEE"),
        ("optional", "EMPLOYEE"),
    ):
        email = f"{name}-{suffix}@example.com"
        accounts[name] = admin.request(
            "/api/v1/users",
            method="POST",
            expected=201,
            body={"email": email, "password": password, "role": role},
        )["id"]
        browser = Browser(hr.base, hr.origin)
        browser.request(
            "/api/v1/auth/login",
            method="POST",
            body={"email": email, "password": password},
        )
        browsers[name] = browser
    department = hr.request(
        "/api/v1/departments",
        method="POST",
        expected=201,
        body={"code": f"ENG-{suffix}", "name": "Smoke Engineering"},
    )
    position = hr.request(
        "/api/v1/positions",
        method="POST",
        expected=201,
        body={"code": f"DEV-{suffix}", "title": "Smoke Developer"},
    )
    base = {"department_id": department["id"], "position_id": position["id"]}
    leader = hr.request(
        "/api/v1/employees",
        method="POST",
        expected=201,
        body={
            **base,
            "employee_code": f"MGR-{suffix}",
            "display_name": "Smoke Manager",
            "user_id": accounts["manager"],
        },
    )
    report = hr.request(
        "/api/v1/employees",
        method="POST",
        expected=201,
        body={
            **base,
            "employee_code": f"EMP-{suffix}",
            "display_name": "Smoke Employee",
            "user_id": accounts["employee"],
            "manager_id": leader["id"],
        },
    )
    for name in ("peer", "subordinate", "optional"):
        hr.request(
            "/api/v1/employees",
            method="POST",
            expected=201,
            body={
                **base,
                "employee_code": f"{name.upper()}-{suffix}",
                "display_name": f"Smoke {name}",
                "user_id": accounts[name],
                "manager_id": report["id"] if name == "subordinate" else None,
            },
        )
    browsers["employee"].request("/api/v1/employees/" + leader["id"], expected=404)
    assert (
        browsers["employee"].request("/api/v1/auth/me")["employee_id"] == report["id"]
    )
    assert browsers["manager"].request("/api/v1/employees")["total"] == 2
    admin.request("/api/v1/employees", expected=403)
    hr.request(
        "/api/v1/employees/" + leader["id"],
        method="PATCH",
        expected=409,
        body={"manager_id": report["id"]},
    )
    review_cycle_smoke(
        admin,
        hr,
        browsers["manager"],
        browsers["employee"],
        report,
        suffix,
        extra_reviewers={
            name: browsers[name] for name in ("peer", "subordinate", "optional")
        },
        organization_base=base,
    )
    hr.request(
        "/api/v1/employees/" + report["id"], method="PATCH", body={"manager_id": None}
    )
    browsers["manager"].request("/api/v1/employees/" + report["id"], expected=404)
    assert (
        browsers["manager"].request("/api/v1/review-cycles", expected=200)["total"] == 0
    )
    print(
        "Organization HTTP smoke passed: references, linking, scope, cycle rejection, transfer."
    )


def review_cycle_smoke(
    admin: Browser,
    hr: Browser,
    manager: Browser,
    employee: Browser,
    report: dict,
    suffix: str,
    *,
    extra_reviewers: dict[str, Browser],
    organization_base: dict,
) -> None:
    defaults = admin.request("/api/v1/settings/scoring")
    admin.request(
        "/api/v1/settings/scoring",
        method="PATCH",
        body={
            "expected_version": defaults["version"],
            "policy": {
                "kpi_weight": "70.00",
                "feedback_weight": "30.00",
                "kpi_cap": "120.00",
            },
        },
    )
    hr.request("/api/v1/settings/scoring", expected=403)
    admin.request("/api/v1/review-cycles", expected=403)
    cycle = hr.request(
        "/api/v1/review-cycles",
        method="POST",
        expected=201,
        body={
            "name": "Smoke cycle",
            "start_date": "2026-10-01",
            "end_date": "2026-12-31",
        },
    )
    path = "/api/v1/review-cycles/" + cycle["id"]
    hr.request(
        path + "/participants",
        method="POST",
        body={
            "expected_version": 1,
            "employee_ids": [report["id"]],
        },
    )
    activated = hr.request(
        path + "/activate", method="POST", body={"expected_version": 2}
    )
    assert (
        activated["status"] == "ACTIVE" and activated["policy"]["kpi_cap"] == "120.00"
    )
    assert manager.request(path)["participant_count"] == 1
    definition = hr.request(
        "/api/v1/kpis",
        method="POST",
        expected=201,
        body={
            "code": f"SALES-{suffix}",
            "name": "Smoke sales",
            "unit": "VND",
            "direction": "HIGHER_IS_BETTER",
        },
    )
    allocation_path = f"/api/v1/employees/{report['id']}/kpis?cycle_id={cycle['id']}"
    body = {
        "expected_evidence_version": 2,
        "items": [
            {
                "definition_id": definition["id"],
                "target": "100.0000",
                "weight": "100.00",
            },
        ],
    }
    manager.request(allocation_path, method="PUT", body=body, csrf=False, expected=403)
    assigned = manager.request(allocation_path, method="PUT", body=body)
    assert assigned["participant"]["evidence_version"] == 3
    assert assigned["items"][0]["actual"] is None
    actual_path = "/api/v1/employee-kpis/" + assigned["items"][0]["id"]
    actual = manager.request(
        actual_path,
        method="PATCH",
        body={
            "expected_evidence_version": 3,
            "actual": "0.0000",
        },
    )
    assert actual["participant"]["evidence_version"] == 4
    assert employee.request(allocation_path)["items"][0]["actual"] == "0.0000"
    employee.request(
        actual_path,
        method="PATCH",
        body={
            "expected_evidence_version": 4,
            "actual": "9.0000",
        },
        expected=403,
    )
    manager.request(
        allocation_path,
        method="PUT",
        body={**body, "expected_evidence_version": 3},
        expected=409,
    )
    hr.request(
        "/api/v1/kpis/" + definition["id"],
        method="PATCH",
        body={
            "expected_version": 1,
            "name": "Changed catalog name",
        },
    )
    assert (
        employee.request(allocation_path)["items"][0]["definition"]["name"]
        == "Smoke sales"
    )
    latest = admin.request("/api/v1/settings/scoring")
    admin.request(
        "/api/v1/settings/scoring",
        method="PATCH",
        body={
            "expected_version": latest["version"],
            "policy": {"kpi_cap": "150.00"},
        },
    )
    assert employee.request(path)["policy"]["kpi_cap"] == "120.00"
    hr.request(
        path + "/close",
        method="POST",
        body={"expected_version": activated["version"]},
        expected=409,
    )
    print(
        "Cycle/KPI HTTP smoke passed: defaults, activation, snapshots, allocation, "
        "actual zero, scope, CSRF and stale version."
    )
    feedback_smoke(
        admin,
        hr,
        manager,
        employee,
        extra_reviewers,
        actual["participant"],
        cycle,
        organization_base,
        suffix,
    )
    performance_smoke(
        admin,
        hr,
        manager,
        employee,
        extra_reviewers["optional"],
        actual["participant"],
        cycle,
        actual_path,
    )


def performance_smoke(
    admin: Browser,
    hr: Browser,
    manager: Browser,
    employee: Browser,
    optional: Browser,
    participant: dict,
    cycle: dict,
    actual_path: str,
) -> None:
    context = hr.request("/api/v1/feedback-context?participant_id=" + participant["id"])
    assignment = hr.request(
        "/api/v1/feedback-assignments",
        method="POST",
        expected=201,
        body={
            "participant_id": participant["id"],
            "reviewer_id": optional.request("/api/v1/auth/me")["id"],
            "relationship": "PEER",
            "required": False,
            "expected_evidence_version": context["evidence_version"],
        },
    )
    base = "/api/v1/performance/" + participant["employee_id"]
    path = base + "?cycle_id=" + cycle["id"]
    payload = {
        "cycle_id": cycle["id"],
        "expected_evidence_version": assignment["evidence_version"],
    }
    manager.request(
        base + "/calculate", method="POST", body=payload, csrf=False, expected=403
    )
    calculated = manager.request(
        base + "/calculate", method="POST", body=payload, expected=201
    )
    assert calculated["current_result"]["final_score"] == "24.00"
    assert hr.request(base + "/calculate", method="POST", body=payload)["reused"]
    admin.request(path, expected=403)
    optional.request(path, expected=404)
    manager.request(
        actual_path,
        method="PATCH",
        body={
            "expected_evidence_version": payload["expected_evidence_version"],
            "actual": "90.0000",
        },
    )
    stale = employee.request(path)
    assert stale["state"] == "STALE" and stale["current_result"] is None
    payload["expected_evidence_version"] += 1
    report = hr.request(base + "/calculate", method="POST", body=payload)
    assert report["current_result"]["final_score"] == "87.00"
    review = "/api/v1/reviews/" + report["review_id"]
    assert employee.request(review + "/revisions")["total"] == 2
    assert employee.request(review + "/revisions/1")["final_score"] == "24.00"
    manager.request(review + "/finalization-context", expected=403)
    final_context = hr.request(review + "/finalization-context")
    assert final_context["open_optional_count"] == 1
    body = {
        "expected_evidence_version": final_context["evidence_version"],
        "expected_calculation_version": final_context["calculation_version"],
        "acknowledge_open_optional_count": 0,
    }
    hr.request(review + "/finalize", method="POST", body=body, expected=409)
    body["acknowledge_open_optional_count"] = 1
    hr.request(review + "/finalize", method="POST", body=body, csrf=False, expected=403)
    finalized = hr.request(review + "/finalize", method="POST", body=body)
    assert finalized["state"] == "FINALIZED"
    hr.request(review + "/finalize", method="POST", body=body, expected=409)
    manager.request(
        actual_path,
        method="PATCH",
        body={
            "expected_evidence_version": body["expected_evidence_version"],
            "actual": "99.0000",
        },
        expected=409,
    )
    optional.request(
        "/api/v1/feedback",
        method="POST",
        body={
            "assignment_id": assignment["id"],
            "expected_assignment_version": 1,
            "expected_evidence_version": body["expected_evidence_version"],
            "rating": 5,
            "comment": "Late feedback",
        },
        expected=409,
    )
    cycle_path = "/api/v1/review-cycles/" + cycle["id"]
    hr.request(
        cycle_path + "/close",
        method="POST",
        body={"expected_version": finalized["cycle_version"]},
        csrf=False,
        expected=403,
    )
    hr.request(
        cycle_path + "/close",
        method="POST",
        body={"expected_version": finalized["cycle_version"]},
    )
    assert employee.request(path)["state"] == "FINALIZED"
    ai_path = "/api/v1/performance/" + report["review_id"] + "/ai-analysis"
    ai_state = employee.request(ai_path)
    assert ai_state["state"] == "NOT_GENERATED" and not ai_state["configured"]
    manager.request(ai_path + "?audience=HR_PRIVATE", expected=403)
    admin.request(ai_path, expected=403)
    hr.request(ai_path, method="POST", expected=503, body={
        "client_request_id": str(uuid4()),
        "expected_calculation_version": report["current_result"]["calculation_version"],
        "expected_evidence_version": report["evidence_version"],
    })
    assert hr.request(review + "/ai-analyses")["total"] == 0
    print("AI keyless HTTP smoke passed: saved-read endpoint, private scope, disabled POST, no attempt.")
    next_cycle = hr.request(
        "/api/v1/review-cycles",
        method="POST",
        expected=201,
        body={
            "name": "Next smoke cycle",
            "start_date": "2027-01-01",
            "end_date": "2027-03-31",
        },
    )
    next_path = "/api/v1/review-cycles/" + next_cycle["id"]
    hr.request(
        next_path + "/participants",
        method="POST",
        body={"expected_version": 1, "employee_ids": [participant["employee_id"]]},
    )
    assert (
        hr.request(
            next_path + "/activate", method="POST", body={"expected_version": 2}
        )["status"]
        == "ACTIVE"
    )
    print(
        "Performance HTTP smoke passed: exact scores, reuse, stale/recalculate, two revisions, optional acknowledgement, atomic finalization, evidence locks, closure and next activation."
    )
    closed_dashboard = hr.request("/api/v1/dashboard?cycle_id=" + cycle["id"])
    assert closed_dashboard["average"] == "87.00" and closed_dashboard["sample_size"] == 1
    assert closed_dashboard["finalized"] == 1 and closed_dashboard["awaiting_completion"] == 0
    assert len(closed_dashboard["recent_activities"]) == 3
    for browser in (hr, manager, employee):
        dashboard = browser.request("/api/v1/dashboard")
        assert dashboard["selected_cycle"]["id"] == next_cycle["id"]
        assert dashboard["average"] is None and dashboard["not_calculated"] == 1
        assert browser.request("/api/v1/ai-reports")["total"] == 0
    manager.request("/api/v1/ai-reports?audience=HR_PRIVATE", expected=403)
    admin.request("/api/v1/ai-reports", expected=403)
    assert "participants" not in admin.request("/api/v1/dashboard")
    print("Phase 8 HTTP smoke passed: scoped dashboard, sanitized activity, saved AI list and role boundaries.")


def feedback_smoke(
    admin: Browser,
    hr: Browser,
    manager: Browser,
    employee: Browser,
    extra: dict[str, Browser],
    participant: dict,
    cycle: dict,
    organization_base: dict,
    suffix: str,
) -> None:
    for name, browser in (("ADMIN", admin), ("HR", hr)):
        identity = browser.request("/api/v1/auth/me")
        hr.request(
            "/api/v1/employees",
            method="POST",
            expected=201,
            body={
                **organization_base,
                "employee_code": f"{name}-{suffix}",
                "display_name": f"Smoke {name}",
                "user_id": identity["id"],
            },
        )
    for browser, relationship in (
        (employee, "SELF"),
        (manager, "MANAGER"),
        (extra["peer"], "PEER"),
        (extra["subordinate"], "SUBORDINATE"),
        (admin, "PEER"),
    ):
        identity = browser.request("/api/v1/auth/me")
        row = hr.request(
            "/api/v1/feedback-assignments",
            method="POST",
            expected=201,
            body={
                "participant_id": participant["id"],
                "reviewer_id": identity["id"],
                "relationship": relationship,
                "required": True,
                "expected_evidence_version": participant["evidence_version"],
            },
        )
        payload = {
            "assignment_id": row["id"],
            "expected_assignment_version": row["version"],
            "expected_evidence_version": row["evidence_version"],
            "rating": 4,
            "comment": "Private smoke feedback",
        }
        browser.request(
            "/api/v1/feedback", method="POST", body=payload, csrf=False, expected=403
        )
        sent = browser.request(
            "/api/v1/feedback", method="POST", body=payload, expected=201
        )
        browser.request("/api/v1/feedback", method="POST", body=payload, expected=409)
        participant["evidence_version"] = sent["evidence_version"]
        own = browser.request("/api/v1/feedback-assignments")["items"]
        assert len(own) == 1 and "reviewer_id" not in own[0]
    # Retain a real CANCELLED row for restart/persistence acceptance.
    optional = hr.request(
        "/api/v1/feedback-assignments",
        method="POST",
        expected=201,
        body={
            "participant_id": participant["id"],
            "reviewer_id": hr.request("/api/v1/auth/me")["id"],
            "relationship": "PEER",
            "required": False,
            "expected_evidence_version": participant["evidence_version"],
        },
    )
    hr.request(
        "/api/v1/feedback-assignments/" + optional["id"],
        method="DELETE",
        body={
            "expected_assignment_version": optional["version"],
            "expected_evidence_version": optional["evidence_version"],
            "reason_code": "WRONG_SELECTION",
        },
    )
    path = f"/api/v1/employees/{participant['employee_id']}/feedback?cycle_id={cycle['id']}"
    summary = employee.request(path)
    assert summary["ready"] and summary["count"] == 5 and summary["mean"] == "4.00"
    assert all(
        g["suppressed"] and g["count"] is None
        for g in summary["groups"]
        if g["relationship"] in ("PEER", "SUBORDINATE")
    )
    manager_summary = manager.request(path)
    assert manager_summary["own_submission"]["comment"] == "Private smoke feedback"
    extra["peer"].request(path, expected=404)
    admin.request(path, expected=403)
    admin.request("/api/v1/feedback-assignments?view=administration", expected=403)
    assert hr.request("/api/v1/feedback-assignments?view=administration")["total"] == 6
    print(
        "Feedback HTTP smoke passed: real SELF/MANAGER/PEER/SUBORDINATE/ADMIN reviewers, "
        "CSRF, replay, HR raw scope, required coverage, suppression and retained cancellation."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-project", required=True)
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--origin", default="http://localhost:3000")
    args = parser.parse_args()
    admin_password, initial, replacement = [secrets.token_urlsafe(24) for _ in range(3)]
    suffix = secrets.token_hex(5)
    admin_email, hr_email = f"admin-{suffix}@example.com", f"hr-{suffix}@example.com"
    bootstrap = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            args.compose_project,
            "--env-file",
            ".env.example",
            "exec",
            "-T",
            "api",
            "python",
            "-m",
            "app.cli.create_admin",
            "--email",
            admin_email,
            "--password-stdin",
        ],
        input=f"{admin_password}\n{admin_password}\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if bootstrap.returncode:
        raise RuntimeError("Compose administrator bootstrap failed")
    admin = Browser(args.base_url, args.origin)
    admin.request(
        "/api/v1/auth/login",
        method="POST",
        body={
            "email": admin_email,
            "password": admin_password,
        },
    )
    cookies = {cookie.name: cookie for cookie in admin.jar}
    assert cookies["insighthr_access"].path == "/"
    assert cookies["insighthr_refresh"].path == "/api/v1/auth/refresh"
    assert cookies["insighthr_csrf"].path == "/"
    assert cookies["insighthr_access"].has_nonstandard_attr("HttpOnly")
    assert cookies["insighthr_refresh"].has_nonstandard_attr("HttpOnly")
    assert not cookies["insighthr_csrf"].has_nonstandard_attr("HttpOnly")
    assert admin.request("/api/v1/auth/me")["role"] == "ADMIN"
    admin.request(
        "/api/v1/users",
        method="POST",
        expected=201,
        body={
            "email": hr_email,
            "password": initial,
            "role": "HR",
        },
    )
    current, other = (
        Browser(args.base_url, args.origin),
        Browser(args.base_url, args.origin),
    )
    for browser in (current, other):
        browser.request(
            "/api/v1/auth/login",
            method="POST",
            body={
                "email": hr_email,
                "password": initial,
            },
        )
    current.request("/api/v1/users", expected=403)
    organization_smoke(admin, current, suffix)
    current.request("/api/v1/auth/refresh", method="POST", csrf=False, expected=403)
    current.request(
        "/api/v1/auth/change-password",
        method="POST",
        expected=204,
        body={
            "old_password": initial,
            "new_password": replacement,
        },
    )
    other.request("/api/v1/auth/me", expected=401)
    current.request("/api/v1/auth/refresh", method="POST", expected=204)
    stale = Browser(args.base_url, args.origin)
    for cookie in current.jar:
        stale.jar.set_cookie(cookie)
    current.request("/api/v1/auth/logout", method="POST", expected=204)
    stale.request("/api/v1/auth/me", expected=401)
    stale.request("/api/v1/auth/refresh", method="POST", expected=401)
    print(
        "Authentication HTTP smoke passed: "
        "bootstrap, proxy, roles, CSRF, password, refresh, logout."
    )


if __name__ == "__main__":
    main()
