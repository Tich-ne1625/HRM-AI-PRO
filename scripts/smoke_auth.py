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
                raise RuntimeError(f"Unexpected status for {method} {path}: {response.status}")
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
    for name, role in (("manager", "MANAGER"), ("employee", "EMPLOYEE")):
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
    browsers["employee"].request("/api/v1/employees/" + leader["id"], expected=404)
    assert browsers["employee"].request("/api/v1/auth/me")["employee_id"] == report["id"]
    assert browsers["manager"].request("/api/v1/employees")["total"] == 2
    admin.request("/api/v1/employees", expected=403)
    hr.request(
        "/api/v1/employees/" + leader["id"],
        method="PATCH",
        expected=409,
        body={"manager_id": report["id"]},
    )
    review_cycle_smoke(admin, hr, browsers["manager"], browsers["employee"], report, suffix)
    hr.request("/api/v1/employees/" + report["id"], method="PATCH", body={"manager_id": None})
    browsers["manager"].request("/api/v1/employees/" + report["id"], expected=404)
    assert browsers["manager"].request("/api/v1/review-cycles", expected=200)["total"] == 0
    print("Organization HTTP smoke passed: references, linking, scope, cycle rejection, transfer.")


def review_cycle_smoke(
    admin: Browser,
    hr: Browser,
    manager: Browser,
    employee: Browser,
    report: dict,
    suffix: str,
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
    activated = hr.request(path + "/activate", method="POST", body={"expected_version": 2})
    assert activated["status"] == "ACTIVE" and activated["policy"]["kpi_cap"] == "120.00"
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
    assert employee.request(allocation_path)["items"][0]["definition"]["name"] == "Smoke sales"
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
    hr.request(path + "/close", method="POST", expected=404)
    print(
        "Cycle/KPI HTTP smoke passed: defaults, activation, snapshots, allocation, "
        "actual zero, scope, CSRF and stale version."
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
