from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


SETUP = {
    "family_name": "测试家庭",
    "parent": {"name": "妈妈", "avatar": "🦉", "pin": "1234"},
    "child": {"name": "小满", "avatar": "🌱", "pin": "5678"},
    "create_samples": False,
}


def setup(client):
    response = client.post("/api/setup", json=SETUP)
    assert response.status_code == 200, response.text
    return response.json()


def child_id(client) -> int:
    response = client.get("/api/auth/members")
    return next(
        member["id"] for member in response.json() if member["role"] == "child"
    )


def login_child(client):
    cid = child_id(client)
    response = client.post(
        "/api/auth/login", json={"member_id": cid, "pin": "5678"}
    )
    assert response.status_code == 200, response.text
    return cid


def login_parent(client):
    member_id = next(
        member["id"]
        for member in client.get("/api/auth/members").json()
        if member["role"] == "parent"
    )
    response = client.post(
        "/api/auth/login", json={"member_id": member_id, "pin": "1234"}
    )
    assert response.status_code == 200, response.text


def make_task(client, child, **overrides):
    payload = {
        "child_id": child,
        "title": "每日任务",
        "description": "",
        "points": 10,
        "task_type": "daily",
    }
    payload.update(overrides)
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def approve_submission(client, submission_id):
    response = client.post(
        f"/api/submissions/{submission_id}/review",
        json={"approve": True, "note": "很好"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def local_noon_utc(days_ago: int = 0) -> datetime:
    tz = ZoneInfo("Asia/Shanghai")
    day = datetime.now(tz).date() - timedelta(days=days_ago)
    return datetime.combine(day, time(12), tzinfo=tz).astimezone(timezone.utc)


def test_streak_bonus_starts_on_threshold_day_and_affects_level(client):
    setup(client)
    cid = child_id(client)
    task = make_task(
        client,
        cid,
        points=10,
        streak_threshold_days=3,
        streak_bonus_percent=25,
    )

    session_factory = client.app.state.session_factory
    with session_factory() as db:
        from app.models import Submission, Task

        db_task = db.get(Task, task["id"])
        db_task.created_at = local_noon_utc(3)
        for offset in (2, 1):
            day = local_noon_utc(offset)
            db.add(
                Submission(
                    task_id=db_task.id,
                    child_id=cid,
                    submitted_by_id=cid,
                    status="approved",
                    note="补录",
                    period_key=day.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat(),
                    submitted_at=day,
                    points_awarded=10,
                )
            )
        db.commit()

    login_child(client)
    submitted = client.post("/api/submissions", data={"task_id": str(task["id"])})
    assert submitted.status_code == 200, submitted.text
    submission_id = submitted.json()["id"]

    login_parent(client)
    approved = approve_submission(client, submission_id)
    assert approved["points_awarded"] == 10
    assert approved["bonus_points"] == 3
    assert approved["bonus_percent"] == 25

    points = client.get(f"/api/points?child_id={cid}").json()
    assert points["lifetime_earned"] == 13
    kinds = {row["kind"] for row in points["transactions"]}
    assert "streak_bonus" in kinds
    task_now = client.get(f"/api/tasks?child_id={cid}").json()[0]
    assert task_now["streak_days"] >= 3
    assert task_now["bonus_active"] is True


def test_non_applicable_weekday_rejects_submission(client):
    setup(client)
    cid = child_id(client)
    today = datetime.now(ZoneInfo("Asia/Shanghai")).isoweekday()
    other = 1 if today != 1 else 2
    task = make_task(client, cid, active_weekdays=[other])
    login_child(client)
    response = client.post("/api/submissions", data={"task_id": str(task["id"])})
    assert response.status_code == 400
    assert "适用日" in response.json()["detail"]


def test_level_thresholds_and_badges(client):
    setup(client)
    cid = child_id(client)
    task = make_task(client, cid, points=20, task_type="once")
    login_child(client)
    submitted = client.post("/api/submissions", data={"task_id": str(task["id"])})
    login_parent(client)
    approve_submission(client, submitted.json()["id"])

    config = [
        {"level": level, "required_points": 10 * (level - 1)}
        for level in range(2, 21)
    ]
    updated = client.put("/api/levels", json={"thresholds": config})
    assert updated.status_code == 200, updated.text
    points = client.get(f"/api/points?child_id={cid}").json()
    assert points["level"] == 3
    level_badges = [badge for badge in points["badges"] if badge["kind"] == "level"]
    assert {badge["level"] for badge in level_badges} == {2, 3}

    invalid = [
        {"level": level, "required_points": 100}
        for level in range(2, 21)
    ]
    rejected = client.put("/api/levels", json={"thresholds": invalid})
    assert rejected.status_code == 400


def test_staged_goal_points_and_task_count_badges(client):
    setup(client)
    cid = child_id(client)
    goal = client.post(
        "/api/goals",
        json={
            "child_id": cid,
            "title": "作业达人",
            "target_value": 20,
            "progress_mode": "points",
            "badge_name": "作业完成",
            "stages": [
                {"threshold_value": 10, "badge_name": "作业起步"},
            ],
        },
    )
    assert goal.status_code == 200, goal.text
    goal = goal.json()
    assert goal["progress_mode"] == "points"
    first = make_task(client, cid, title="作业一", points=10, goal_id=goal["id"], task_type="once")
    second = make_task(client, cid, title="作业二", points=10, goal_id=goal["id"], task_type="once")

    login_child(client)
    first_sub = client.post("/api/submissions", data={"task_id": str(first["id"])})
    second_sub = client.post("/api/submissions", data={"task_id": str(second["id"])})
    login_parent(client)
    approve_submission(client, first_sub.json()["id"])
    detail = client.get(f"/api/goals?child_id={cid}").json()[0]
    assert detail["progress_value"] == 10
    assert detail["stages"][0]["badge_awarded"] is True
    assert detail["status"] == "active"

    approve_submission(client, second_sub.json()["id"])
    detail = client.get(f"/api/goals?child_id={cid}").json()[0]
    assert detail["status"] == "completed"
    assert detail["completed_at"] is not None

    points = client.get(f"/api/points?child_id={cid}").json()
    achievements = [
        badge for badge in points["badges"] if badge["kind"] == "achievement"
    ]
    assert len(achievements) == 2
    assert {badge["name"] for badge in achievements} == {"作业起步", "作业完成"}

    counted = client.post(
        "/api/goals",
        json={
            "child_id": cid,
            "title": "打卡次数",
            "target_value": 2,
            "progress_mode": "task_count",
            "stages": [{"threshold_value": 1}],
        },
    )
    assert counted.status_code == 200, counted.text
    counted = counted.json()
    assert counted["target_points"] == 0
    third = make_task(client, cid, title="次数一", points=1, goal_id=counted["id"], task_type="once")
    fourth = make_task(client, cid, title="次数二", points=1, goal_id=counted["id"], task_type="once")
    login_child(client)
    third_sub = client.post("/api/submissions", data={"task_id": str(third["id"])})
    fourth_sub = client.post("/api/submissions", data={"task_id": str(fourth["id"])})
    login_parent(client)
    approve_submission(client, third_sub.json()["id"])
    approve_submission(client, fourth_sub.json()["id"])
    counted_detail = next(
        row
        for row in client.get(f"/api/goals?child_id={cid}").json()
        if row["id"] == counted["id"]
    )
    assert counted_detail["status"] == "completed"
    assert counted_detail["progress_value"] == 2

    bad_stage = client.post(
        "/api/goals",
        json={
            "child_id": cid,
            "title": "错误阶段",
            "target_value": 10,
            "stages": [{"threshold_value": 10}],
        },
    )
    assert bad_stage.status_code == 400


def test_child_wish_parent_lists_reward(client):
    setup(client)
    cid = child_id(client)
    login_child(client)
    created = client.post(
        "/api/wishes",
        data={
            "title": "乐高",
            "emoji": "🧱",
            "reason": "想拼一座城堡",
            "expected_points": 300,
        },
    )
    assert created.status_code == 200, created.text
    wish = created.json()
    assert wish["status"] == "pending"

    login_parent(client)
    pending = client.get("/api/wishes?status=pending").json()
    assert len(pending) == 1
    listed = client.post(
        f"/api/wishes/{wish['id']}/list",
        json={
            "title": "乐高城堡",
            "emoji": "🧱",
            "value": 300,
            "unit": "points",
            "multiplier": 1.0,
            "stock": 1,
        },
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["status"] == "listed"
    assert listed.json()["reward_id"] is not None
    reward = client.get(f"/api/rewards/{listed.json()['reward_id']}").json()
    assert reward["title"] == "乐高城堡"
    assert reward["cost_points"] == 300

    login_child(client)
    mine = client.get("/api/wishes").json()
    assert mine[0]["status"] == "listed"
    assert mine[0]["reward_title"] == "乐高城堡"


def test_reward_specific_tasks_show_aggregate_progress(client):
    setup(client)
    cid = child_id(client)
    reward = client.post(
        "/api/rewards",
        json={
            "title": "电影夜",
            "emoji": "🎬",
            "value": 30,
            "unit": "points",
            "multiplier": 1.0,
            "stock": -1,
        },
    ).json()
    task = make_task(client, cid, points=10, reward_id=reward["id"], task_type="once")
    assert task["reward_id"] == reward["id"]

    login_child(client)
    submitted = client.post("/api/submissions", data={"task_id": str(task["id"])})
    login_parent(client)
    approve_submission(client, submitted.json()["id"])
    detail = client.get(f"/api/rewards/{reward['id']}").json()
    assert detail["reward_task_points"] == 10
    assert detail["reward_task_count"] == 1
    assert detail["linked_tasks"][0]["id"] == task["id"]

    client.delete(f"/api/rewards/{reward['id']}")
    tasks = client.get(f"/api/tasks?child_id={cid}&include_inactive=true").json()
    assert tasks[0]["reward_id"] is None


def test_manual_and_auto_matching_on_redemption(client):
    setup(client)
    cid = child_id(client)
    reward = client.post(
        "/api/rewards",
        json={
            "title": "远行望远镜",
            "emoji": "🔭",
            "value": 100,
            "unit": "points",
            "multiplier": 1.0,
            "stock": 1,
            "is_long_term": True,
            "auto_match_percent": 50,
        },
    ).json()
    client.post(
        "/api/points/adjust",
        json={"child_id": cid, "delta": 50, "note": "启动"},
    )
    login_child(client)
    locked = client.post(
        "/api/savings/lock",
        json={"reward_id": reward["id"], "amount": 20},
    )
    assert locked.status_code == 200, locked.text

    login_parent(client)
    match = client.post(
        "/api/matches",
        json={"reward_id": reward["id"], "child_id": cid, "amount": 30, "note": "妈妈支持"},
    )
    assert match.status_code == 200, match.text

    detail = client.get(f"/api/rewards/{reward['id']}?child_id={cid}").json()
    assert detail["manual_matched_points"] == 30
    assert detail["auto_match_points"] == 10
    assert detail["saved_points"] == 60
    assert detail["remaining_points"] == 40

    revoke = client.post(f"/api/matches/{match.json()['id']}/revoke")
    assert revoke.status_code == 200
    assert client.get(f"/api/rewards/{reward['id']}?child_id={cid}").json()[
        "manual_matched_points"
    ] == 0
    second_match = client.post(
        "/api/matches",
        json={"reward_id": reward["id"], "child_id": cid, "amount": 30},
    )
    assert second_match.status_code == 200, second_match.text

    client.post(
        "/api/points/adjust",
        json={"child_id": cid, "delta": 10, "note": "补足"},
    )
    login_child(client)
    requested = client.post("/api/redemptions", json={"reward_id": reward["id"]})
    assert requested.status_code == 200, requested.text
    redemption = requested.json()

    login_parent(client)
    approved = client.post(
        f"/api/redemptions/{redemption['id']}/review",
        json={"approve": True, "note": "达成"},
    )
    assert approved.status_code == 200, approved.text
    points = client.get(f"/api/points?child_id={cid}").json()
    assert points["balance"] == 0
    assert points["locked"] == 0
    matches = client.get(
        f"/api/matches?child_id={cid}&reward_id={reward['id']}&include_closed=true"
    ).json()
    sources = {(row["source"], row["status"]) for row in matches}
    assert ("manual", "used") in sources
    assert ("auto", "used") in sources


def test_statistics_and_csv_export(client):
    setup(client)
    cid = child_id(client)
    task = make_task(client, cid, points=10, task_type="once")
    login_child(client)
    submitted = client.post("/api/submissions", data={"task_id": str(task["id"])})
    login_parent(client)
    approve_submission(client, submitted.json()["id"])

    stats = client.get(f"/api/stats?child_id={cid}&period=week")
    assert stats.status_code == 200, stats.text
    data = stats.json()
    assert data["task_points"] == 10
    assert data["net_points"] == 10
    assert data["task_completion"]["approved"] >= 1
    assert data["has_data"] is True
    assert len(data["buckets"]) == 7

    exported = client.get(f"/api/stats/export?child_id={cid}&period=month")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    assert "任务获得" in exported.text

    login_child(client)
    own = client.get("/api/stats?period=week")
    assert own.status_code == 200
    assert own.json()["child_id"] == cid
    assert client.get("/api/stats/export?period=week").status_code == 403


def test_icon_upload_and_controlled_access(client):
    setup(client)
    cid = child_id(client)
    uploaded = client.post(
        "/api/icons",
        files={"file": ("goal.jpg", b"fake-image", "image/jpeg")},
    )
    assert uploaded.status_code == 200, uploaded.text
    path = uploaded.json()["path"]
    goal = client.post(
        "/api/goals",
        json={
            "child_id": cid,
            "title": "带图标目标",
            "target_value": 10,
            "icon_image_path": path,
        },
    )
    assert goal.status_code == 200, goal.text
    assert goal.json()["icon_url"].startswith("/api/media/")
    media = client.get(goal.json()["icon_url"])
    assert media.status_code == 200

    login_child(client)
    assert client.get(goal.json()["icon_url"]).status_code == 200
    assert client.post(
        "/api/icons",
        files={"file": ("goal.jpg", b"fake-image", "image/jpeg")},
    ).status_code == 403
