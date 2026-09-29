from datetime import datetime
from typing import Optional

from django.http import HttpRequest
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from desk.auth_utils import bearer_auth, create_access_token, verify_password
from desk.models import LimitChange, OffsetSubmission, ToleranceLimit, User
from desk.services import change_limit

api = NinjaAPI(title="数控刀补复核台", version="1.0")


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
    limit_um: Optional[int]
    status: str
    verdict: str
    created_at: datetime
    reviewed_at: Optional[datetime]


class LimitOut(Schema):
    limit_um: int
    updated_at: Optional[datetime]


class LimitChangeIn(Schema):
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
        limit_um=row.limit_um,
        status=row.status,
        verdict=row.verdict or "",
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


def _change_to_out(row: LimitChange) -> LimitChangeOut:
    return LimitChangeOut(
        id=row.id,
        old_limit_um=row.old_limit_um,
        new_limit_um=row.new_limit_um,
        changed_by=row.changed_by.username if row.changed_by else None,
        changed_at=row.changed_at,
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
    rows = OffsetSubmission.objects.all()[:200]
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
    limit = ToleranceLimit.get()
    return LimitOut(limit_um=limit.limit_um, updated_at=limit.updated_at)


@api.get("/limit/changes", response=list[LimitChangeOut], auth=bearer_auth)
def list_limit_changes(request: HttpRequest):
    rows = LimitChange.objects.select_related("changed_by").all()[:200]
    return [_change_to_out(r) for r in rows]


@api.post("/limit", response=LimitOut, auth=bearer_auth)
def update_limit(request: HttpRequest, body: LimitChangeIn):
    user: User = request.auth
    if not user.can_write:
        raise HttpError(403, "只有操作员能改上限，复核员只读")
    if body.limit_um < 0:
        raise HttpError(400, "上限不能为负数")
    limit, _ = change_limit(user, body.limit_um)
    return LimitOut(limit_um=limit.limit_um, updated_at=limit.updated_at)
