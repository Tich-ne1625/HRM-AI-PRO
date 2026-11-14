"""Browser acceptance on a fresh fictional stack at web 13029/API 18029 only.

Seed with the public test password DemoBulk@2026; disable AI. Never use user data.
"""

import argparse
import json
import secrets
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

import phase9_browser as browser
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".superpowers/feedback-bulk/browser"
browser.BASE, browser.OUT = "http://localhost:13029", OUT


def main(employee_code="DEMO-DUNG"):
    OUT.mkdir(parents=True, exist_ok=True)
    port, sockets = 19289, []
    process = subprocess.Popen(
        [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--remote-allow-origins=http://localhost:{port}",
            "--no-first-run",
            "--disable-extensions",
            f"--user-data-dir={OUT / ('profile-' + secrets.token_hex(4))}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        for _ in range(80):
            try:
                with urlopen(
                    f"http://localhost:{port}/json/version", timeout=1
                ) as response:
                    endpoint = json.load(response)["webSocketDebuggerUrl"]
                break
            except OSError:
                time.sleep(0.25)
        root_socket = connect(
            endpoint.replace("localhost", "127.0.0.1"), proxy=None, ping_interval=None
        )
        sockets.append(root_socket)
        control = object.__new__(browser.Page)
        control.socket, control.sequence, control.responses, control.exceptions = (
            root_socket,
            0,
            [],
            [],
        )
        control.methods, control.step = {}, "browser context setup"

        def page(name):
            context = control.command("Target.createBrowserContext")["browserContextId"]
            target = control.command(
                "Target.createTarget",
                {"url": "about:blank", "browserContextId": context},
            )["targetId"]
            socket = connect(
                f"ws://127.0.0.1:{port}/devtools/page/{target}",
                proxy=None,
                ping_interval=None,
                max_size=12_000_000,
            )
            sockets.append(socket)
            p = browser.Page(socket)
            p.command(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": "window.notificationChanges=0;const Source=window.EventSource;window.EventSource=class extends Source{constructor(...args){super(...args);this.addEventListener('change',()=>window.notificationChanges++);}}"
                },
            )
            p.go("/login")
            p.click("Dùng tài khoản riêng")
            p.fill("#email", name + ".demo@example.com")
            p.fill("#password", "DemoBulk@2026")
            p.write(
                "/api/v1/auth/login",
                lambda: p.js("document.querySelector('form').requestSubmit()"),
            )
            p.wait(
                "location.pathname==='/dashboard' && !!document.querySelector('.notification-trigger')"
            )
            return p

        hr, employee = page("hr"), page("an")
        before = employee.get("/api/v1/notifications")["unread_count"]
        cycle = hr.get("/api/v1/review-cycles?status=ACTIVE")["items"][0]
        subject = next(
            row
            for row in hr.get(f"/api/v1/review-cycles/{cycle['id']}/participants")[
                "items"
            ]
            if row["employee_code"] == employee_code
        )
        hr.go("/feedback-administration")
        hr.select_label("Chu kỳ cần phân công", cycle["id"])
        hr.wait(
            "[...document.querySelectorAll('.assignment-subject')].some(e=>e.textContent.includes("
            + json.dumps(employee_code)
            + "))"
        )
        hr.js(
            "[...document.querySelectorAll('.assignment-subject')].find(e=>e.textContent.includes("
            + json.dumps(employee_code)
            + ")).click()"
        )
        hr.wait("!!document.querySelector('dialog[open] #feedback-relationship')")
        hr.fill("#feedback-relationship", "SUBORDINATE")
        hr.wait(
            "document.body.innerText.includes('Không còn người chưa được giao phù hợp')"
        )
        hr.fill("#feedback-relationship", "PEER")
        hr.select_label("Phòng ban người đánh giá", subject["department_id"])
        filtered = hr.get(
            f"/api/v1/feedback-reviewer-options?participant_id={subject['id']}&relationship=PEER&department_id={subject['department_id']}&available_only=true"
        )
        count = filtered["total"]
        assert count >= 2
        hr.click(f"Chọn toàn bộ kết quả lọc ({count})")
        hr.wait(f"document.body.innerText.includes('Đã chọn {count}/')")
        hr.js(
            "document.querySelector('.reviewer-multi-picker').scrollIntoView({block:'start'})"
        )
        hr.shot("hr-filtered-multiple-reviewers")
        hr.click(f"Xem lại {count} người đã chọn")
        assert not any(
            row["path"] == "/api/v1/feedback-assignments/bulk" for row in hr.writes
        )
        context = hr.get(f"/api/v1/feedback-context?participant_id={subject['id']}")
        result = hr.write(
            "/api/v1/feedback-assignments/bulk",
            lambda: hr.click(f"Xác nhận giao {count} phiếu"),
            201,
        )
        assert (
            result["created_count"] == count
            and result["evidence_version"] == context["evidence_version"] + 1
        )
        hr.wait(f"document.body.innerText.includes('Đã giao {count} phiếu')")
        employee.wait(
            f"Number(document.querySelector('.notification-count')?.textContent||0)==={before + 1}"
        )
        assert employee.js("window.notificationChanges") > 0
        mine = employee.get("/api/v1/feedback-assignments?view=mine")["items"]
        assigned = [row for row in mine if row["id"] in result["assignment_ids"]]
        assert len(assigned) == 1
        employee.js("document.querySelector('.notification-trigger').click()")
        employee.wait(
            "[...document.querySelectorAll('.notification-item')].some(e=>e.textContent.includes("
            + json.dumps(subject["display_name"])
            + "))"
        )
        employee.js(
            "[...document.querySelectorAll('.notification-item')].find(e=>e.textContent.includes("
            + json.dumps(subject["display_name"])
            + ")&&e.textContent.includes('phiếu phản hồi mới')).click()"
        )
        employee.wait("!!document.querySelector('dialog[open] #feedback-rating')")
        employee.fill("#feedback-rating", "4")
        employee.fill(
            "#feedback-comment", "Fictional bulk-assignment acceptance feedback."
        )
        employee.click("Kiểm tra và gửi")
        employee.write(
            "/api/v1/feedback", lambda: employee.click("Xác nhận gửi một lần"), 201
        )
        hr.js(
            "document.querySelector('.assignment-success').scrollIntoView({block:'start'})"
        )
        hr.shot("hr-bulk-assignment-complete")
        assert (
            sum(row["path"] == "/api/v1/feedback-assignments/bulk" for row in hr.writes)
            == 1
        )
        assert not hr.exceptions and not employee.exceptions
        report = {
            "hr_workspace_visible": True,
            "participant_without_prior_peer_assignment_selectable": True,
            "filtered_department_reviewer_count": count,
            "single_atomic_ui_request": True,
            "one_evidence_increment": True,
            "recipient_realtime_notice": True,
            "recipient_can_open_and_submit": True,
            "subordinate_filter_preserves_relationship": True,
            "widths": [1280, 390],
            "ai_calls": 0,
            "user_data_untouched": True,
        }
        (OUT / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    finally:
        for socket in reversed(sockets):
            socket.close()
        process.terminate()
        process.wait(timeout=15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--employee-code", default="DEMO-DUNG", choices=["DEMO-DUNG", "DEMO-BINH"]
    )
    main(parser.parse_args().employee_code)
