import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import services, timeutils
from app.auth import hash_pin
from app.models import Family, Member
from test_mvp import child_id, login_child, login_parent, make_goal, setup
from test_p1 import make_task


TASKS = "/api/parent-tasks"
HOME = "/api/child/home"
DASHBOARD = "/api/parent/dashboard"
SECOND_PARENT_PIN = "2345"
OTHER_CHILD_PIN = "6789"
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _json(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def _member(client, role, name, pin):
    return _json(client.post("/api/members", json={"role": role, "name": name, "pin": pin}))


@pytest.fixture
def household(client):
    parent = setup(client)["member"]
    cid = child_id(client)
    child = next(member for member in _json(client.get("/api/members")) if member["id"] == cid)
    return parent, child


@pytest.fixture
def clock(monkeypatch):
    from app import parent_tasks

    now = datetime.now(timezone.utc)

    def set_time(value):
        nonlocal now
        now = value

    for module in (parent_tasks, services, timeutils):
        monkeypatch.setattr(module, "utcnow", lambda: now.astimezone(timezone.utc))
    return set_time


def _task_payload(child, parent, **overrides):
    return {
        "child_id": child["id"],
        "assigned_parent_id": parent["id"],
        "title": "Water the plants",
        "description": "Check the soil first",
        "points": 150,
        "task_type": "daily",
        "active_weekdays": list(range(1, 8)),
        "active": True,
        **overrides,
    }


def _create_task(client, child, parent, **overrides):
    return _json(client.post(TASKS, json=_task_payload(child, parent, **overrides)), 201)


def _submit(client, task, note="Done"):
    return client.post(f"{TASKS}/{task['id']}/submissions", json={"note": note})


def _remind(client, task):
    return client.post(f"{TASKS}/{task['id']}/reminders")


def _confirm(client, submission):
    return client.patch(f"/api/parent-task-submissions/{submission['id']}/confirmation")


def _card(view, task):
    return next(card for card in view["parent_tasks"] if card["task"]["id"] == task["id"])


def _contributions(report):
    return {row["member_id"]: row for row in report["contributors"]}


def _contributor(member, points, completed_tasks):
    return {
        "member_id": member["id"],
        "member_name": member["name"],
        "role": member["role"],
        "points": points,
        "completed_tasks": completed_tasks,
    }


def test_parent_task_workflow_preserves_child_progress_and_funds_redemption(client, household, clock):
    parent, child = household
    cid = child["id"]
    # Three personal earning dates give the wish a nonempty estimate to compare.
    today = datetime.now(timezone.utc).astimezone(SHANGHAI).replace(
        hour=12, minute=0, second=0, microsecond=0,
    )
    goal = make_goal(client, cid)
    personal = make_task(client, cid, goal_id=goal["id"], points=10)
    for days_ago in (2, 1, 0):
        clock(today - timedelta(days=days_ago))
        result = _json(client.post("/api/submissions", data={"task_id": personal["id"]}))
        assert result["status"] == "approved"
    reward = _json(client.post("/api/rewards", json={
        "title": "A test wish", "value": 150, "unit": "points", "is_long_term": True,
    }))
    _json(client.patch(f"/api/members/{cid}", json={"approval_required": False}))
    task = _create_task(client, child, parent)
    dashboard = _json(client.get(DASHBOARD))
    assert _card(dashboard, task)["status"] == "todo"
    assert [row["id"] for row in dashboard["today_tasks"]] == [personal["id"]]
    week_before = dashboard["children"][0]["week_earned"]

    login_child(client)
    before = _json(client.get(HOME))
    assert before["balance"] == 30
    assert before["long_term_rewards"][0]["estimated_days"] is not None
    assert _card(before, task)["status"] == "todo"
    assert before["parent_task_confirmations"] == []
    rate_before = _json(client.get("/api/stats"))["task_completion"]
    for _ in range(2):
        reminder = _remind(client, task)
        assert reminder.status_code == 204, reminder.text
        assert reminder.content == b""

    login_parent(client)
    assert _card(_json(client.get(DASHBOARD)), task)["reminded"] is True
    submission = _json(_submit(client, task, "Finished before lunch"), 201)
    assert submission["confirmed_at"] is None
    assert submission["period_key"] == today.date().isoformat()
    duplicate = _submit(client, task)
    assert duplicate.status_code == 409, duplicate.text
    edited = _json(client.patch(f"{TASKS}/{task['id']}", json={"title": "New title", "points": 1}))
    assert (edited["title"], edited["points"]) == ("New title", 1)
    dashboard = _json(client.get(DASHBOARD))
    assert dashboard["pending_submissions"] == []
    assert _card(dashboard, task)["status"] == "pending"
    assert _card(dashboard, task)["reminded"] is False

    login_child(client)
    pending = _json(client.get(HOME))
    assert pending["balance"] == 30
    assert _card(pending, task)["status"] == "pending"
    assert pending["parent_task_confirmations"] == [{
        "id": submission["id"], "task_id": task["id"], "task_title": task["title"],
        "child_id": cid, "assigned_parent_id": parent["id"], "assigned_parent_name": parent["name"],
        "points": 150, "note": "Finished before lunch", "period_key": today.date().isoformat(),
        "submitted_at": submission["submitted_at"], "confirmed_at": None,
    }]
    confirmed = _json(_confirm(client, submission))
    assert confirmed["confirmed_at"] is not None
    assert (confirmed["task_title"], confirmed["points"]) == (task["title"], 150)
    assert _confirm(client, submission).status_code == 409
    after = _json(client.get(HOME))
    assert after["parent_task_confirmations"] == []
    assert _card(after, task)["status"] == "done"
    assert (after["balance"], after["available"], after["locked"]) == (180, 180, 0)
    for field in ("lifetime_earned", "level", "level_progress", "streak_days", "badges", "goals", "today_tasks"):
        assert after[field] == before[field], field
    assert after["long_term_rewards"][0]["estimated_days"] == before["long_term_rewards"][0]["estimated_days"]
    assert _json(client.get("/api/stats"))["task_completion"] == rate_before
    for ledger in (after["recent_transactions"], _json(client.get("/api/points"))["transactions"]):
        rows = [row for row in ledger if row["kind"] == "parent_task"]
        assert [(row["delta"], row["contributor_name"]) for row in rows] == [(150, parent["name"])]

    _json(client.post("/api/savings/lock", json={"reward_id": reward["id"], "amount": 150}))
    points = _json(client.get("/api/points"))
    assert (points["balance"], points["available"], points["locked"]) == (180, 30, 150)
    redemption = _json(client.post("/api/redemptions", json={"reward_id": reward["id"]}))
    login_parent(client)
    dashboard = _json(client.get(DASHBOARD))
    assert _card(dashboard, task)["status"] == "done"
    assert dashboard["children"][0]["week_earned"] == week_before + 150
    _json(client.post(f"/api/redemptions/{redemption['id']}/review", json={"approve": True}))
    points = _json(client.get(f"/api/points?child_id={cid}"))
    assert (points["balance"], points["available"], points["locked"], points["lifetime_earned"]) == (30, 30, 0, 30)


def test_statistics_and_csv_attribute_task_points_and_counts_to_actual_contributors(client, household, clock):
    parent, child = household
    second = _member(client, "parent", "Second helper", SECOND_PARENT_PIN)
    other_child = _member(client, "child", "Other child", OTHER_CHILD_PIN)
    personal = make_task(client, child["id"], points=20, streak_threshold_days=1, streak_bonus_percent=50)
    rejected = make_task(client, child["id"], points=90, task_type="once")
    earned = _create_task(client, child, second, points=40, task_type="once")
    zero = _create_task(client, child, parent, points=0, task_type="once")
    pending = _create_task(client, child, second, points=100)

    login_parent(client, second["id"], pin=SECOND_PARENT_PIN)
    proxy = _json(client.post("/api/submissions", data={"task_id": personal["id"]}))
    assert (proxy["status"], proxy["bonus_points"]) == ("approved", 10)
    paid_submission = _json(_submit(client, earned), 201)
    _json(_submit(client, pending), 201)

    login_child(client)
    denied = _json(client.post("/api/submissions", data={"task_id": rejected["id"]}))
    _json(_confirm(client, paid_submission))
    login_parent(client)
    _json(client.post(f"/api/submissions/{denied['id']}/review", json={"approve": False}))
    zero_submission = _json(_submit(client, zero), 201)
    _json(client.post("/api/points/adjust", json={
        "child_id": child["id"], "delta": 7, "note": "Test adjustment",
    }))
    login_child(client)
    _json(_confirm(client, zero_submission))
    report = _json(client.get("/api/stats?period=week"))
    assert (report["task_points"], report["bonus_points"], report["parent_task_points"]) == (20, 10, 40)
    assert (report["adjusted_points"], report["net_points"], report["task_completion"]["approved"]) == (7, 77, 1)
    expected = {
        member["id"]: _contributor(member, points, count)
        for member, points, count in ((child, 30, 1), (parent, 0, 1), (second, 40, 1))
    }
    assert _contributions(report) == expected
    assert client.get("/api/stats/export").status_code == 403

    login_parent(client)
    params = {"child_id": child["id"], "period": "week"}
    assert _contributions(_json(client.get("/api/stats", params=params))) == expected
    other = _json(client.get("/api/stats", params={**params, "child_id": other_child["id"]}))
    assert other["parent_task_points"] == 0
    assert all(row["points"] == row["completed_tasks"] == 0 for row in other["contributors"])
    export = client.get("/api/stats/export", params=params)
    assert export.status_code == 200, export.text
    rows = list(csv.reader(io.StringIO(export.content.decode("utf-8-sig"))))
    for row in expected.values():
        assert any(row["member_name"] in cells and cells[-2:] == [
            str(row["points"]), str(row["completed_tasks"]),
        ] for cells in rows), rows
    assert any(len(cells) == 2 and cells[1] == "40" for cells in rows), rows


def test_independent_confirmation_requests_can_credit_only_once(client, household):
    parent, child = household
    task = _create_task(client, child, parent, points=42, task_type="once")
    submission = _json(_submit(client, task), 201)
    assert submission["period_key"] == "once"
    barrier = Barrier(2)

    def confirm_together(session):
        barrier.wait(timeout=10)
        return _confirm(session, submission)

    with TestClient(client.app) as first, TestClient(client.app) as second:
        login_child(first)
        login_child(second)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(confirm_together, (first, second)))
    assert sorted(response.status_code for response in responses) == [200, 409], [r.text for r in responses]
    points = _json(client.get(f"/api/points?child_id={child['id']}"))
    assert points["balance"] == 42
    assert [row["delta"] for row in points["transactions"] if row["kind"] == "parent_task"] == [42]
    report = _json(client.get(f"/api/stats?child_id={child['id']}"))
    assert _contributions(report)[parent["id"]] == _contributor(parent, 42, 1)


def test_late_confirmation_uses_local_confirmation_week_even_after_disabling_task_and_parent(client, household, clock):
    parent, child = household
    assigned = _member(client, "parent", "Late helper", SECOND_PARENT_PIN)
    clock(datetime(2026, 11, 1, 15, 55, tzinfo=timezone.utc))  # Sunday in Shanghai
    task = _create_task(client, child, assigned, points=18, task_type="weekly")
    reminder_only = _create_task(client, child, assigned, title="Tomorrow too", active_weekdays=[1, 7])
    sunday_only = _create_task(client, child, assigned, title="Sunday only", active_weekdays=[7])
    login_child(client)
    assert _remind(client, reminder_only).status_code == 204
    login_parent(client, assigned["id"], pin=SECOND_PARENT_PIN)
    pending = _json(_submit(client, task), 201)
    assert pending["period_key"] == "2026-W44"
    assert _card(_json(client.get(DASHBOARD)), reminder_only)["reminded"] is True

    clock(datetime(2026, 11, 1, 16, 5, tzinfo=timezone.utc))  # Monday in Shanghai
    dashboard = _json(client.get(DASHBOARD))
    assert _card(dashboard, task)["period_key"] == "2026-W45"
    assert _card(dashboard, task)["status"] == "todo"
    assert _card(dashboard, reminder_only)["reminded"] is False
    assert _card(dashboard, reminder_only)["period_key"] == "2026-11-02"
    assert sunday_only["id"] not in {row["task"]["id"] for row in dashboard["parent_tasks"]}
    assert _submit(client, sunday_only).status_code in (400, 409)
    login_parent(client, parent["id"])
    _json(client.patch(f"{TASKS}/{task['id']}", json={"active": False, "points": 0}))
    _json(client.patch(f"/api/members/{assigned['id']}", json={"is_active": False}))

    login_child(client)
    home = _json(client.get(HOME))
    assert home["balance"] == 0
    assert task["id"] not in {row["task"]["id"] for row in home["parent_tasks"]}
    assert [row["id"] for row in home["parent_task_confirmations"]] == [pending["id"]]
    confirmed = _json(_confirm(client, pending))
    assert (confirmed["period_key"], confirmed["points"]) == ("2026-W44", 18)
    old = _json(client.get("/api/stats?period=week&anchor=2026-11-01"))
    new = _json(client.get("/api/stats?period=week&anchor=2026-11-02"))
    assert old["parent_task_points"] == 0
    assert all(row["completed_tasks"] == 0 for row in old["contributors"])
    assert new["parent_task_points"] == new["net_points"] == 18
    assert _contributions(new)[assigned["id"]] == _contributor(assigned, 18, 1)


def test_parent_task_roles_filters_and_family_boundaries(client, household):
    parent, child = household
    second = _member(client, "parent", "Other helper", SECOND_PARENT_PIN)
    other_child = _member(client, "child", "Other beneficiary", OTHER_CHILD_PIN)
    task = _create_task(client, child, parent, title="Private task")
    other_task = _create_task(client, other_child, second, title="Other task")
    assert {row["id"] for row in _json(client.get(TASKS))} == {task["id"], other_task["id"]}
    assert [row["id"] for row in _json(client.get(TASKS, params={"child_id": child["id"]}))] == [task["id"]]
    for patch in ({"child_id": other_child["id"]}, {"assigned_parent_id": second["id"]}, {"task_type": "weekly"}):
        response = client.patch(f"{TASKS}/{task['id']}", json=patch)
        assert response.status_code == 422, response.text
    for override in ({"child_id": second["id"]}, {"assigned_parent_id": other_child["id"]}):
        response = client.post(TASKS, json=_task_payload(child, parent, **override))
        assert response.status_code in (400, 404, 422), response.text

    login_child(client)
    assert client.get(TASKS).status_code == 403
    assert client.post(TASKS, json=_task_payload(child, parent)).status_code == 403
    assert client.patch(f"{TASKS}/{task['id']}", json={"points": 0}).status_code == 403
    assert _submit(client, task).status_code == 403
    assert _remind(client, task).status_code == 204
    login_parent(client, second["id"], pin=SECOND_PARENT_PIN)
    assert [row["task"]["id"] for row in _json(client.get(DASHBOARD))["parent_tasks"]] == [other_task["id"]]
    assert _submit(client, task).status_code == 403
    assert _remind(client, task).status_code == 403

    login_parent(client)
    submission = _json(_submit(client, task, "Private completion note"), 201)
    assert _confirm(client, submission).status_code == 403
    login_parent(client, other_child["id"], pin=OTHER_CHILD_PIN)
    assert _remind(client, task).status_code in (403, 404)
    assert _confirm(client, submission).status_code in (403, 404)
    home = _json(client.get(HOME))
    assert [row["task"]["id"] for row in home["parent_tasks"]] == [other_task["id"]]
    assert home["parent_task_confirmations"] == []

    # Seed an unrelated household only inside the temporary test database.
    with client.app.state.session_factory() as db:
        family = Family(name="Unrelated test family")
        db.add(family)
        db.flush()
        outsider = Member(family_id=family.id, name="Outside helper", role="parent", pin_hash=hash_pin("3456"))
        db.add(outsider)
        db.flush()
        outsider_id = outsider.id
        db.commit()
    login_parent(client, outsider_id, pin="3456")
    assert _json(client.get(TASKS)) == []
    assert _json(client.get(DASHBOARD))["parent_tasks"] == []
    assert client.get(TASKS, params={"child_id": child["id"]}).status_code == 404
    assert client.patch(f"{TASKS}/{task['id']}", json={"points": 0}).status_code == 404
    assert _submit(client, task).status_code == 404
    cross_family = client.post(TASKS, json=_task_payload(child, parent))
    missing = client.post(TASKS, json=_task_payload(child, parent, child_id=-1))
    assert cross_family.status_code == missing.status_code == 400
    assert cross_family.json() == missing.json()

    login_child(client)
    assert _json(client.get(HOME))["balance"] == 0
    _json(_confirm(client, submission))
