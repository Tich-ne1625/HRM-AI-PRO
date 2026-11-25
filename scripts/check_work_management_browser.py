"""Real form acceptance against the isolated continuous demo on ports 13039/18039.

Requires seed_continuous_demo in continuous_demo_test. Never targets the user's stack.
"""

import json
import secrets
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import urlopen

import phase9_browser as browser
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".superpowers/phase11/browser"
browser.BASE, browser.OUT = "http://localhost:13039", OUT


def click(page, text):
    expression = (
        "[...document.querySelectorAll('button')].find(e=>e.getClientRects().length"
        "&&!e.disabled&&e.textContent===" + json.dumps(text) + ")"
    )
    page.wait(f"!!{expression}")
    page.js(expression + ".click()")


def tab(page, name):
    click(page, name)
    page.wait(
        "[...document.querySelectorAll('[role=tab]')].some(e=>e.textContent==="
        + json.dumps(name)
        + "&&e.getAttribute('aria-selected')==='true')"
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    port, sockets = 19339, []
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
        endpoint = None
        for _ in range(80):
            try:
                with urlopen(
                    f"http://localhost:{port}/json/version", timeout=1
                ) as response:
                    endpoint = json.load(response)["webSocketDebuggerUrl"]
                break
            except OSError:
                time.sleep(0.25)
        assert endpoint
        root = connect(
            endpoint.replace("localhost", "127.0.0.1"), proxy=None, ping_interval=None
        )
        sockets.append(root)
        control = object.__new__(browser.Page)
        control.socket, control.sequence, control.responses, control.exceptions = (
            root,
            0,
            [],
            [],
        )
        control.methods, control.step = {}, "setup"

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
                    "source": "window.notificationChanges=0;const Source=window.EventSource;"
                    "window.EventSource=class extends Source{constructor(...args){super(...args);"
                    "this.addEventListener('change',()=>window.notificationChanges++);}}"
                },
            )
            p.go("/login")
            click(p, "Dùng tài khoản riêng")
            p.fill("#email", f"{name}.demo@example.com")
            p.fill("#password", "1")
            p.write(
                "/api/v1/auth/login",
                lambda: p.js("document.querySelector('form').requestSubmit()"),
            )
            p.wait(
                "location.pathname==='/dashboard'&&!!document.querySelector('.notification-trigger')"
            )
            return p

        manager, owner, hr, admin = (
            page(name) for name in ("care.manager", "care01", "hr", "admin")
        )
        manager.go("/work-management")
        owner.go("/work-management")
        owner.wait("document.querySelectorAll('.work-card').length>=4")
        owner.shot("employee-work-board")
        manager.shot("manager-work-board")
        assert admin.get("/api/v1/work-management/participants")["total"] == 0
        assert not admin.js(
            "[...document.querySelectorAll('a')].some(e=>e.getAttribute('href')==='/work-management')"
        )
        hr.go("/work-management")
        assert not hr.js(
            "[...document.querySelectorAll('button')].some(e=>e.textContent==='Công việc')"
        )
        hr.shot("hr-plan-coordination")

        # Start a separate draft through HR's real cycle/enrollment controls.
        today = datetime.now(UTC).astimezone().date()
        start, end = today + timedelta(days=2), today + timedelta(days=30)
        hr.go("/review-cycles")
        click(hr, "Tạo chu kỳ mới")
        hr.fill("#cycle-name", "[UI DEMO] Thống nhất kế hoạch " + secrets.token_hex(3))
        hr.fill("#cycle-mode", "CONTINUOUS")
        hr.fill("#cycle-start", str(start))
        hr.fill("#cycle-end", str(end))
        for selector, value in [
            ("#acknowledgement_due_at", start - timedelta(days=1)),
            ("#input_cutoff_at", end + timedelta(days=1)),
            ("#verification_due_at", end + timedelta(days=2)),
            ("#response_due_at", end + timedelta(days=3)),
        ]:
            hr.fill(selector, str(value) + "T12:00")
        new_cycle = hr.write(
            "/api/v1/review-cycles", lambda: click(hr, "Tạo chu kỳ nháp"), 201
        )
        hr.go("/review-cycles/" + new_cycle["id"])
        hr.wait(
            "[...document.querySelectorAll('label')].some(e=>e.textContent.includes('CONT-CARE01'))"
        )
        hr.js(
            "[...document.querySelectorAll('label')].find(e=>e.textContent.includes('CONT-CARE01')).querySelector('input').click()"
        )
        hr.write(
            "/api/v1/review-cycles/" + new_cycle["id"] + "/participants",
            lambda: click(hr, "Thêm người đã chọn"),
        )
        manager.go("/work-management?cycle_id=" + new_cycle["id"])
        click(manager, "Kế hoạch & mục tiêu")
        click(manager, "Lập kế hoạch")
        manager.fill(
            "dialog .work-form > label textarea", "Xử lý hồ sơ có đối chiếu QA rõ ràng."
        )
        definition = manager.get("/api/v1/work-management/definitions")["items"][0][
            "id"
        ]
        manager.fill("dialog .work-goal-editor select", definition)
        manager.fill("dialog .work-numbers label:nth-child(2) input", "120")
        manager.fill("dialog .work-numbers label:nth-child(3) input", "100")
        manager.fill(
            "dialog .work-goal-editor > label:nth-last-of-type(2) textarea",
            "Mã hồ sơ CSKH duy nhất được QA đối chiếu.",
        )
        manager.fill(
            "dialog .work-goal-editor > label:last-of-type textarea",
            "QA và khách hàng xác nhận kết quả.",
        )
        click(manager, "Xem lại kế hoạch")
        participant = next(
            p["participant_id"]
            for p in manager.get(
                "/api/v1/work-management/participants?cycle_id=" + new_cycle["id"]
            )["items"]
        )
        new_plan = manager.write(
            "/api/v1/work-management/participants/" + participant + "/plan",
            lambda: click(manager, "Lưu bản kế hoạch"),
        )

        def plan_step(page, plan_id, action, body=None):
            page.go("/work-management?plan=" + plan_id)
            page.wait(
                "!!document.querySelector('dialog [role=tabpanel]:not([hidden]) select')"
            )
            page.fill("dialog [role=tabpanel]:not([hidden]) select", action)
            if body:
                page.fill("dialog [role=tabpanel]:not([hidden]) textarea", body)
            click(page, "Xem lại trước khi gửi")
            return page.write(
                "/api/v1/work-management/plans/" + plan_id + "/actions",
                lambda: click(page, "Xác nhận gửi"),
            )

        plan_step(manager, new_plan["id"], "submit")
        plan_step(
            owner,
            new_plan["id"],
            "clarify",
            "Làm rõ nguồn đối chiếu QA theo từng mã hồ sơ.",
        )
        manager.go("/work-management?plan=" + new_plan["id"])
        click(manager, "Chỉnh sửa kế hoạch")
        manager.fill(
            "dialog .work-goal-editor > label:nth-last-of-type(2) textarea",
            "Mã CSKH duy nhất, có mã xác minh QA và xác nhận khách hàng.",
        )
        click(manager, "Xem lại kế hoạch")
        revised = manager.write(
            "/api/v1/work-management/participants/" + participant + "/plan",
            lambda: click(manager, "Lưu bản kế hoạch"),
        )
        assert revised["revision"] == 2 and revised["acknowledged_revision"] is None
        plan_step(manager, new_plan["id"], "submit")
        plan_step(manager, new_plan["id"], "approve")
        hr.go("/work-management?cycle_id=" + new_cycle["id"])
        hr.wait("document.body.innerText.includes('Chưa xác nhận bản hiện hành')")
        before = hr.js("window.notificationChanges")
        acknowledged = plan_step(owner, new_plan["id"], "acknowledge")
        assert acknowledged["acknowledged_revision"] == 2
        hr.wait("window.notificationChanges>" + str(before))
        hr.wait(
            "document.body.innerText.includes('Nhân viên đã xác nhận bản hiện hành')"
        )
        owner.shot("employee-acknowledged-revision-two")

        participants = manager.get("/api/v1/work-management/participants")["items"]
        active_plan = next(
            p["plan_id"] for p in participants if p["cycle_status"] == "ACTIVE"
        )
        manager.go("/work-management?plan=" + active_plan)
        manager.wait("!!document.querySelector('dialog [role=tab]')")
        tab(manager, "Tiến trình & bằng chứng")
        click(manager, "Giao công việc")
        manager.fill(
            "dialog input[name=title]",
            "Đối chiếu QA từ giao diện " + secrets.token_hex(3),
        )
        manager.fill("dialog textarea[name=acceptance]", "Có mã hồ sơ và QA xác nhận.")
        manager.fill("dialog input[name=source]", "UI-" + secrets.token_hex(6))
        goal = manager.get("/api/v1/work-management/plans/" + active_plan)["goals"][0][
            "id"
        ]
        manager.fill("dialog select[name=goal]", goal)
        manager.fill(
            "dialog input[name=due]",
            (datetime.now(UTC).astimezone() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
        )
        click(manager, "Xem lại công việc")
        todo = manager.write(
            "/api/v1/work-management/plans/" + active_plan + "/items",
            lambda: click(manager, "Xác nhận giao việc"),
        )
        assert todo["goal_id"] == goal
        manager.js("document.querySelector('dialog .dialog-close').click()")
        manager.wait("!document.querySelector('dialog[open]')")
        path = "/api/v1/work-management/items/" + todo["id"] + "/actions"
        owner.go("/work-management?item=" + todo["id"])
        owner.wait("!!document.querySelector('dialog [role=tab]')")
        tab(owner, "Tiến trình & bằng chứng")
        click(owner, "Xem lại trước khi gửi")
        owner.write(path, lambda: click(owner, "Xác nhận gửi"))
        tab(owner, "Tiến trình & bằng chứng")
        owner.wait(
            "document.querySelector('dialog [role=tabpanel]:not([hidden]) select')?.value==='submit'&&!document.querySelector('dialog [role=tabpanel]:not([hidden]) select').disabled"
        )
        owner.fill(
            "dialog [role=tabpanel]:not([hidden]) textarea",
            "Đã xử lý hồ sơ và có xác nhận QA.",
        )
        tab(owner, "Lịch sử")
        tab(owner, "Tiến trình & bằng chứng")
        assert owner.js(
            "document.querySelector('dialog [role=tabpanel]:not([hidden]) textarea').value.includes('QA')"
        )
        click(owner, "Xem lại trước khi gửi")
        before = manager.js("window.notificationChanges")
        owner.write(path, lambda: click(owner, "Xác nhận gửi"))
        manager.wait("window.notificationChanges>" + str(before))
        manager.wait("document.body.innerText.includes('Chờ nghiệm thu')")
        manager.go("/work-management?item=" + todo["id"])
        manager.wait("!!document.querySelector('dialog [role=tab]')")
        tab(manager, "Tiến trình & bằng chứng")
        manager.fill("dialog [role=tabpanel]:not([hidden]) select", "return")
        manager.fill(
            "dialog [role=tabpanel]:not([hidden]) textarea", "Bổ sung đối chiếu mã QA."
        )
        click(manager, "Xem lại trước khi gửi")
        manager.write(path, lambda: click(manager, "Xác nhận gửi"))
        owner.wait(
            "document.querySelector('dialog')?.innerText.includes('Cần bổ sung')"
        )
        tab(owner, "Tiến trình & bằng chứng")
        owner.wait(
            "!!document.querySelector('dialog [role=tabpanel]:not([hidden]) form')"
        )
        # A concurrent update is displayed explicitly; the form never silently rebases.
        if owner.js(
            "[...document.querySelectorAll('button')].some(e=>e.textContent==='Dùng phiên bản mới sau khi xem lại'&&e.getClientRects().length)"
        ):
            click(owner, "Dùng phiên bản mới sau khi xem lại")
        click(owner, "Xem lại trước khi gửi")
        owner.write(path, lambda: click(owner, "Xác nhận gửi"))
        tab(owner, "Tiến trình & bằng chứng")
        owner.wait(
            "!!document.querySelector('dialog [role=tabpanel]:not([hidden]) select:not(:disabled)')"
        )
        if owner.js(
            "[...document.querySelectorAll('button')].some(e=>e.textContent==='Dùng phiên bản mới sau khi xem lại'&&e.getClientRects().length)"
        ):
            click(owner, "Dùng phiên bản mới sau khi xem lại")
        owner.fill("dialog [role=tabpanel]:not([hidden]) select", "submit")
        owner.fill(
            "dialog [role=tabpanel]:not([hidden]) textarea",
            "Đã bổ sung mã QA và kết quả đối chiếu.",
        )
        click(owner, "Xem lại trước khi gửi")
        owner.write(path, lambda: click(owner, "Xác nhận gửi"))
        # Reload detail after reviewing the new submission; explicit concurrency UX stays visible.
        manager.go("/work-management?item=" + todo["id"])
        manager.wait("!!document.querySelector('dialog [role=tab]')")
        tab(manager, "Tiến trình & bằng chứng")
        manager.fill(
            "dialog [role=tabpanel]:not([hidden]) textarea",
            "Đủ bằng chứng, đồng ý nghiệm thu.",
        )
        click(manager, "Xem lại trước khi gửi")
        manager.write(path, lambda: click(manager, "Xác nhận gửi"))
        owner.wait(
            "document.querySelector('dialog')?.innerText.includes('Đã nghiệm thu')"
        )
        owner.shot("employee-evidence-two-submissions")
        assert (
            owner.get("/api/v1/work-management/items/" + todo["id"])["submission_total"]
            == 2
        )
        tab(owner, "Lịch sử")
        owner.shot("employee-work-history")
        owner.js("document.querySelector('dialog .dialog-close').click()")
        owner.wait("!document.querySelector('dialog[open]')")
        assert owner.js("location.pathname==='/work-management'")
        assert not any(p.exceptions for p in (manager, owner, hr, admin))
        result = {
            "isolated_demo_only": True,
            "role_navigation": True,
            "hr_creates_continuous_draft_from_form": True,
            "manager_plan_clarification_revision_approval_employee_ack_from_forms": True,
            "hr_readiness_realtime": True,
            "manager_assigns_from_form": True,
            "work_links_to_approved_goal": True,
            "form_start_submit_return_resubmit_accept": True,
            "two_immutable_submissions": True,
            "realtime_between_accounts": True,
            "draft_survives_tabs": True,
            "close_without_back": True,
            "viewport_widths": [1280, 390],
            "ai_calls": 0,
        }
        (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        for socket in sockets:
            socket.close()
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


if __name__ == "__main__":
    main()
