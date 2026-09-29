from datetime import datetime
from typing import Optional

from django.http import HttpRequest
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from desk.auth_utils import bearer_auth, create_access_token, verify_password
from desk.models import LimitChange, OffsetSubmission, ToleranceLimit, User
from desk.services import change_limit

api = NinjaAPI(title="数控刀补复核台", version="1.1")


class HealthOut(Schema):
    status: str


class LoginIn(Schema):
    username: str
    password: str


class LoginOut(Schema):
    token: str
    username: str
    role: str
    can_write: bool


class SubmissionIn(Schema):
    tool_code: str
    offset_um: int


class SubmissionOut(Schema):
    id: int
    tool_code: str
    offset_um: int
    status: str
    verdict: str
    claimed_limit_um: Optional[int]
    created_at: datetime
    reviewed_at: Optional[datetime]


class LimitOut(Schema):
    limit_um: int
    updated_at: Optional[datetime]
    updated_by: Optional[str]


class LimitUpdateIn(Schema):
    limit_um: int


class LimitChangeOut(Schema):
    id: int
    old_limit_um: int
    new_limit_um: int
    changed_by: Optional[str]
    changed_at: datetime


def _to_out(row: OffsetSubmission) -> SubmissionOut:
    return SubmissionOut(
        id=row.id,
        tool_code=row.tool_code,
        offset_um=row.offset_um,
        status=row.status,
        verdict=row.verdict or "",
        claimed_limit_um=row.claimed_limit_um,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


def _limit_out(limit: ToleranceLimit) -> LimitOut:
    return LimitOut(
        limit_um=limit.limit_um,
        updated_at=limit.updated_at,
        updated_by=limit.updated_by.username if limit.updated_by else None,
    )


@api.get("/health", response=HealthOut)
def health(request: HttpRequest):
    return {"status": "ok"}


@api.post("/auth/login", response=LoginOut)
def login(request: HttpRequest, body: LoginIn):
    try:
        user = User.objects.get(username=body.username)
    except User.DoesNotExist:
        raise HttpError(401, "用户名或密码错误")
    if not verify_password(body.password, user.password):
        raise HttpError(401, "用户名或密码错误")
    token = create_access_token(user)
    return {
        "token": token,
        "username": user.username,
        "role": user.role,
        "can_write": user.can_write,
    }


@api.get("/submissions", response=list[SubmissionOut], auth=bearer_auth)
def list_submissions(request: HttpRequest):
    rows = OffsetSubmission.objects.select_related("submitted_by").all()[:200]
    return [_to_out(r) for r in rows]


@api.get("/submissions/{submission_id}", response=SubmissionOut, auth=bearer_auth)
def get_submission(request: HttpRequest, submission_id: int):
    try:
        row = OffsetSubmission.objects.get(pk=submission_id)
    except OffsetSubmission.DoesNotExist:
        raise HttpError(404, "刀补记录不存在")
    return _to_out(row)


@api.post("/submissions", response=SubmissionOut, auth=bearer_auth)
def create_submission(request: HttpRequest, body: SubmissionIn):
    user: User = request.auth
    if not user.can_write:
        raise HttpError(403, "当前账号只读，不能提交刀补")
    tool_code = body.tool_code.strip()
    if not tool_code:
        raise HttpError(400, "刀具编号不能为空")
    row = OffsetSubmission.objects.create(
        tool_code=tool_code,
        offset_um=body.offset_um,
        submitted_by=user,
        status=OffsetSubmission.Status.PENDING,
    )
    return _to_out(row)


@api.get("/limit", response=LimitOut, auth=bearer_auth)
def get_limit(request: HttpRequest):
    # 复核员可看现行数字，但不能改。
    return _limit_out(ToleranceLimit.load())


@api.get("/limit/history", response=list[LimitChangeOut], auth=bearer_auth)
def list_limit_history(request: HttpRequest):
    rows = LimitChange.objects.select_related("changed_by").all()[:100]
    return [
        LimitChangeOut(
            id=r.id,
            old_limit_um=r.old_limit_um,
            new_limit_um=r.new_limit_um,
            changed_by=r.changed_by.username if r.changed_by else None,
            changed_at=r.changed_at,
        )
        for r in rows
    ]


@api.post("/limit", response=LimitOut, auth=bearer_auth)
def update_limit(request: HttpRequest, body: LimitUpdateIn):
    user: User = request.auth
    if not user.can_write:
        # 复核员只能看上限与痕迹，不能改。
        raise HttpError(403, "复核员只读，不能修改合格上限")
    if body.limit_um < 0:
        raise HttpError(400, "合格上限不能为负数")
    limit, _change = change_limit(user, body.limit_um)
    return _limit_out(limit)
