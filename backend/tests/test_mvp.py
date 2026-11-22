from datetime import date


SETUP = {
    "family_name": "测试家庭",
    "parent": {"name": "妈妈", "avatar": "🦉", "pin": "1234"},
    "child": {"name": "小满", "avatar": "🌱", "pin": "5678"},
    "create_samples": False,
}


def setup(client, create_samples: bool = False):
    payload = {**SETUP, "create_samples": create_samples}
    response = client.post("/api/setup", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def members(client):
    response = client.get("/api/members")
    assert response.status_code == 200, response.text
    return response.json()


def child_id(client) -> int:
    response = client.get("/api/auth/members")
    assert response.status_code == 200, response.text
    return next(member["id"] for member in response.json() if member["role"] == "child")


def login_child(client, pin: str = "5678"):
    cid = child_id(client)
    response = client.post(
        "/api/auth/login", json={"member_id": cid, "pin": pin}
    )
    assert response.status_code == 200, response.text
    return cid


def login_parent(client, member_id: int | None = None, pin: str = "1234"):
    if member_id is None:
        member_id = next(
            member["id"] for member in client.get("/api/auth/members").json()
            if member["role"] == "parent"
        )
    response = client.post(
        "/api/auth/login", json={"member_id": member_id, "pin": pin}
    )
    assert response.status_code == 200, response.text


def make_goal(client, child: int, title: str = "阅读目标") -> dict:
    response = client.post(
        "/api/goals",
        json={
            "child_id": child,
            "title": title,
            "emoji": "📚",
            "description": "每天读一点",
            "target_points": 100,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def make_task(
    client,
    child: int,
    title: str = "阅读 20 分钟",
    points: int = 20,
    goal_id: int | None = None,
    task_type: str = "daily",
) -> dict:
    response = client.post(
        "/api/tasks",
        json={
            "child_id": child,
            "goal_id": goal_id,
            "title": title,
            "description": "",
            "points": points,
            "task_type": task_type,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_openapi_contract_has_core_routes_and_no_pin_hash(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    for path in (
        "/api/setup",
        "/api/auth/login",
        "/api/goals",
        "/api/tasks",
        "/api/submissions",
        "/api/points/adjust",
        "/api/rewards",
        "/api/redemptions",
        "/api/savings/lock",
        "/api/child/home",
        "/api/parent/dashboard",
        "/api/backup",
    ):
        assert path in paths
    assert "pin_hash" not in response.text


def test_setup_login_and_roles(client):
    status = client.get("/api/setup/status")
    assert status.status_code == 200
    assert status.json()["needs_setup"] is True

    setup_response = setup(client)
    assert setup_response["member"]["role"] == "parent"

    status = client.get("/api/setup/status")
    assert status.json()["needs_setup"] is False

    duplicate = client.post("/api/setup", json=SETUP)
    assert duplicate.status_code == 409

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["member"]["name"] == "妈妈"

    dashboard = client.get("/api/parent/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["family_name"] == "测试家庭"

    all_members = members(client)
    assert len(all_members) == 2

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    login_child(client)
    assert client.get("/api/child/home").status_code == 200
    assert client.get("/api/parent/dashboard").status_code == 403
    assert client.get("/api/members").status_code == 403


def test_task_submission_review_points_and_quick_log(client):
    setup(client)
    cid = child_id(client)
    goal = make_goal(client, cid)
    task = make_task(client, cid, goal_id=goal["id"], points=20)

    login_child(client)
    home = client.get("/api/child/home").json()
    assert home["balance"] == 0
    assert home["today_tasks"][0]["status"] == "todo"

    submitted = client.post(
        "/api/submissions",
        data={"task_id": str(task["id"]), "note": "我读完了"},
    )
    assert submitted.status_code == 200, submitted.text
    submission = submitted.json()
    assert submission["status"] == "pending"

    duplicate = client.post(
        "/api/submissions",
        data={"task_id": str(task["id"]), "note": "再交一次"},
    )
    assert duplicate.status_code == 400

    assert client.get("/api/points").json()["balance"] == 0

    login_parent(client)
    pending = client.get("/api/submissions/pending")
    assert pending.status_code == 200
    assert len(pending.json()) == 1

    reviewed = client.post(
        f"/api/submissions/{submission['id']}/review",
        json={"approve": True, "note": "读得很认真"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    assert reviewed.json()["points_awarded"] == 20

    points = client.get(f"/api/points?child_id={cid}").json()
    assert points["balance"] == 20
    assert points["available"] == 20
    assert points["lifetime_earned"] == 20
    assert points["level"] == 1

    goal_after = client.get(f"/api/goals?child_id={cid}").json()[0]
    assert goal_after["earned_points"] == 20
    assert goal_after["progress_percent"] == 20

    adjusted = client.post(
        "/api/points/adjust",
        json={"child_id": cid, "delta": 5, "note": "额外奖励"},
    )
    assert adjusted.status_code == 200, adjusted.text
    points = client.get(f"/api/points?child_id={cid}").json()
    assert points["balance"] == 25
    assert points["lifetime_earned"] == 20

    too_much = client.post(
        "/api/points/adjust",
        json={"child_id": cid, "delta": -100, "note": "扣太多"},
    )
    assert too_much.status_code == 400

    quick_task = make_task(client, cid, title="倒垃圾", points=10, task_type="once")
    quick = client.post(
        "/api/submissions",
        data={"task_id": str(quick_task["id"]), "note": "家长代记"},
    )
    assert quick.status_code == 200, quick.text
    assert quick.json()["status"] == "approved"
    points = client.get(f"/api/points?child_id={cid}").json()
    assert points["balance"] == 35

    login_child(client)
    home = client.get("/api/child/home").json()
    daily = next(t for t in home["today_tasks"] if t["id"] == task["id"])
    assert daily["status"] == "done"
    assert home["streak_days"] == 1


def test_child_can_disable_review(client):
    setup(client)
    cid = child_id(client)
    task = make_task(client, cid, points=12)
    response = client.patch(
        f"/api/members/{cid}", json={"approval_required": False}
    )
    assert response.status_code == 200, response.text

    login_child(client)
    submitted = client.post(
        "/api/submissions", data={"task_id": str(task["id"])}
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "approved"
    assert client.get("/api/points").json()["balance"] == 12


def test_reward_multiplier_redemption_and_fulfillment(client):
    setup(client)
    cid = child_id(client)
    reward = client.post(
        "/api/rewards",
        json={
            "title": "现金 100 元",
            "emoji": "💵",
            "value": 100,
            "unit": "yuan",
            "multiplier": 1.5,
            "stock": 2,
        },
    )
    assert reward.status_code == 200, reward.text
    reward = reward.json()
    assert reward["cost_points"] == 150

    client.post(
        "/api/points/adjust",
        json={"child_id": cid, "delta": 150, "note": "测试积分"},
    )

    login_child(client)
    rewards = client.get("/api/rewards").json()
    assert rewards[0]["cost_points"] == 150

    requested = client.post(
        "/api/redemptions", json={"reward_id": reward["id"]}
    )
    assert requested.status_code == 200, requested.text
    redemption = requested.json()
    assert redemption["status"] == "pending"
    assert client.get("/api/points").json()["balance"] == 150

    login_parent(client)
    approved = client.post(
        f"/api/redemptions/{redemption['id']}/review",
        json={"approve": True, "note": "可以兑换"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    points = client.get(f"/api/points?child_id={cid}").json()
    assert points["balance"] == 0
    reward_now = client.get(f"/api/rewards/{reward['id']}").json()
    assert reward_now["stock"] == 1

    fulfilled = client.post(
        f"/api/redemptions/{redemption['id']}/fulfill"
    )
    assert fulfilled.status_code == 200, fulfilled.text
    assert fulfilled.json()["status"] == "fulfilled"


def test_long_term_savings_lock_release_and_redemption(client):
    setup(client)
    cid = child_id(client)
    reward = client.post(
        "/api/rewards",
        json={
            "title": "心仪的电脑",
            "emoji": "💻",
            "value": 500,
            "unit": "points",
            "multiplier": 1.0,
            "stock": 1,
            "is_long_term": True,
        },
    ).json()
    assert reward["is_long_term"] is True

    client.post(
        "/api/points/adjust",
        json={"child_id": cid, "delta": 200, "note": "启动资金"},
    )

    login_child(client)
    home = client.get("/api/child/home").json()
    long_term = next(
        item for item in home["long_term_rewards"] if item["id"] == reward["id"]
    )
    assert long_term["locked_points"] == 0

    locked = client.post(
        "/api/savings/lock",
        json={"reward_id": reward["id"], "amount": 120, "note": "先锁一点"},
    )
    assert locked.status_code == 200, locked.text
    lock = locked.json()
    assert lock["status"] == "active"

    points = client.get("/api/points").json()
    assert points["balance"] == 200
    assert points["available"] == 80
    assert points["locked"] == 120

    no_release = client.post(f"/api/savings/{lock['id']}/release")
    assert no_release.status_code == 403

    login_parent(client)
    released = client.post(f"/api/savings/{lock['id']}/release")
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "released"
    points = client.get(f"/api/points?child_id={cid}").json()
    assert points["available"] == 200
    assert points["locked"] == 0

    login_child(client)
    locked = client.post(
        "/api/savings/lock",
        json={"reward_id": reward["id"], "amount": 120},
    ).json()
    insufficient = client.post(
        "/api/redemptions", json={"reward_id": reward["id"]}
    )
    assert insufficient.status_code == 400

    login_parent(client)
    client.post(
        "/api/points/adjust",
        json={"child_id": cid, "delta": 300, "note": "继续积累"},
    )
    login_child(client)
    requested = client.post(
        "/api/redemptions", json={"reward_id": reward["id"]}
    )
    assert requested.status_code == 200, requested.text
    redemption = requested.json()

    login_parent(client)
    approved = client.post(
        f"/api/redemptions/{redemption['id']}/review",
        json={"approve": True, "note": "达成心愿"},
    )
    assert approved.status_code == 200, approved.text
    points = client.get(f"/api/points?child_id={cid}").json()
    assert points["balance"] == 0
    assert points["locked"] == 0

    locks = client.get(
        f"/api/savings?child_id={cid}&include_released=true"
    ).json()
    assert any(row["id"] == locked["id"] and row["status"] == "redeemed" for row in locks)

    fulfilled = client.post(
        f"/api/redemptions/{redemption['id']}/fulfill"
    )
    assert fulfilled.status_code == 200
    assert fulfilled.json()["status"] == "fulfilled"


def test_photo_validation_and_backup(client):
    setup(client)
    cid = child_id(client)
    task = make_task(client, cid, points=5)
    client.patch(
        f"/api/tasks/{task['id']}", json={"requires_photo": True}
    )

    login_child(client)
    missing = client.post(
        "/api/submissions", data={"task_id": str(task["id"])}
    )
    assert missing.status_code == 400
    invalid = client.post(
        "/api/submissions",
        data={"task_id": str(task["id"])},
        files={"photo": ("note.txt", b"not an image", "text/plain")},
    )
    assert invalid.status_code == 400
    valid = client.post(
        "/api/submissions",
        data={"task_id": str(task["id"])},
        files={"photo": ("proof.jpg", b"fake-jpeg", "image/jpeg")},
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["photo_url"].startswith("/uploads/")

    login_parent(client)
    backup = client.post("/api/backup")
    assert backup.status_code == 200, backup.text
    assert backup.json()["filename"].startswith("wishjar-")


def test_sample_data_and_dashboard(client):
    setup(client, create_samples=True)
    cid = child_id(client)
    dashboard = client.get("/api/parent/dashboard")
    assert dashboard.status_code == 200
    assert len(dashboard.json()["today_tasks"]) >= 3

    login_child(client)
    home = client.get("/api/child/home").json()
    assert len(home["goals"]) == 1
    assert len(home["long_term_rewards"]) == 1
    assert len(home["today_tasks"]) >= 3
    assert home["member"]["id"] == cid


def test_goal_dates_and_member_management(client):
    setup(client)
    cid = child_id(client)
    bad_goal = client.post(
        "/api/goals",
        json={
            "child_id": cid,
            "title": "日期错误",
            "target_points": 10,
            "start_date": "2026-12-31",
            "end_date": "2026-01-01",
        },
    )
    assert bad_goal.status_code == 400

    me = client.get("/api/auth/me").json()["member"]
    self_disable = client.patch(f"/api/members/{me['id']}", json={"is_active": False})
    assert self_disable.status_code == 400

    updated = client.patch(f"/api/members/{cid}", json={"name": "小满满"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "小满满"
