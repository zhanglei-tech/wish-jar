import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from .config import Settings
from .constants import ROLE_CHILD, ROLE_PARENT
from .models import Family, Member


def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        pin.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = stored.split("$", 2)
    except ValueError:
        return False
    if algorithm != "scrypt":
        return False
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.scrypt(
        pin.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32
    )
    return hmac.compare_digest(actual, expected)


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="wishjar-session")


def set_session_cookie(
    response: Response, settings: Settings, member: Member
) -> None:
    token = _serializer(settings).dumps(
        {"member_id": member.id, "family_id": member.family_id}
    )
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.session_max_age_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.cookie_name, path="/")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request):
    session_factory = request.app.state.session_factory
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_current_member(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Member:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Cookie"},
        )
    try:
        data = _serializer(settings).loads(
            token, max_age=settings.session_max_age_days * 24 * 60 * 60
        )
    except (BadSignature, SignatureExpired):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Cookie"},
        )
    member = db.get(Member, data.get("member_id"))
    if (
        member is None
        or not member.is_active
        or member.family_id != data.get("family_id")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效"
        )
    return member


def require_parent(
    current: Member = Depends(get_current_member),
) -> Member:
    if current.role != ROLE_PARENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要家长权限"
        )
    return current


def require_child(
    current: Member = Depends(get_current_member),
) -> Member:
    if current.role != ROLE_CHILD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要孩子账号"
        )
    return current


def resolve_child(db: Session, current: Member, child_id: int) -> Member:
    if current.role == ROLE_CHILD:
        if current.id != child_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="不能访问其他成员的数据"
            )
        return current
    if current.role != ROLE_PARENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="没有访问权限"
        )
    child = db.get(Member, child_id)
    if (
        child is None
        or child.family_id != current.family_id
        or child.role != ROLE_CHILD
    ):
        raise HTTPException(status_code=404, detail="孩子不存在")
    return child


def family_name(db: Session, member: Member) -> str:
    family = db.get(Family, member.family_id)
    return family.name if family else ""
