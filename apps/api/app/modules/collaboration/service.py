from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, and_, case, func, or_, select, true, tuple_, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import ScalarSelect

from app.core.domain_writes import CsrfCheck, authorize_domain_write
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.collaboration.models import ChatMessage, InternalPost, PostComment
from app.modules.collaboration.schemas import ContentInput, PostInput
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.notifications.delivery import signal
from app.modules.notifications.models import Notification
from app.modules.organization.models import Department
from app.modules.users.models import User, UserRole


def department_of(user_id: UUID) -> ScalarSelect[UUID]:
    return (
        select(Employee.department_id)
        .where(Employee.user_id == user_id, Employee.employment_status == EmploymentStatus.ACTIVE)
        .scalar_subquery()
    )


def post_scope(user: User) -> ColumnElement[bool]:
    if user.role in (UserRole.HR, UserRole.ADMIN):
        return InternalPost.id.is_not(None)
    return or_(
        InternalPost.department_id.is_(None), InternalPost.department_id == department_of(user.id)
    )


def available() -> ColumnElement[bool]:
    return and_(
        User.is_active.is_(True),
        or_(Employee.id.is_(None), Employee.employment_status == EmploymentStatus.ACTIVE),
    )


def person(row: Any) -> dict[str, Any]:
    user, employee, department = row
    return {
        "id": user.id,
        "name": employee.display_name if employee else user.email,
        "department_id": employee.department_id if employee else None,
        "department": department.name if department else None,
        "role": user.role,
    }


class CollaborationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.people: dict[UUID, dict[str, Any]] = {}
        self.departments: dict[UUID, str] = {}

    def people_query(self) -> Select[User, Employee, Department]:
        return (
            select(User, Employee, Department)
            .outerjoin(Employee, Employee.user_id == User.id)
            .outerjoin(Department, Department.id == Employee.department_id)
        )

    def preload_content(self, rows: list[InternalPost | PostComment]) -> None:
        identifiers = {row.author_id for row in rows} | {
            UUID(value) for row in rows for value in row.mention_ids
        }
        self.people.update(
            {
                row[0].id: person(row)
                for row in self.session.execute(self.people_query().where(User.id.in_(identifiers)))
            }
        )
        departments = {
            row.department_id for row in rows if isinstance(row, InternalPost) and row.department_id
        }
        self.departments.update(
            dict(
                self.session.execute(
                    select(Department.id, Department.name).where(Department.id.in_(departments))
                ).all()
            )
        )

    def directory(
        self,
        user: User,
        search: str,
        page: int,
        post_id: UUID | None = None,
        own_department: bool = False,
        department_id: UUID | None = None,
    ) -> dict[str, Any]:
        with self.session.begin():
            query = self.people_query().where(available(), User.id != user.id)
            if post_id:
                post = self.get_post(user, post_id)
                if post.department_id:
                    query = query.where(
                        or_(
                            Employee.department_id == post.department_id,
                            User.role.in_((UserRole.HR, UserRole.ADMIN)),
                        )
                    )
            elif own_department or department_id:
                query = query.where(
                    or_(
                        Employee.department_id == (department_id or department_of(user.id)),
                        User.role.in_((UserRole.HR, UserRole.ADMIN)),
                    )
                )
            if search:
                term = (
                    "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                )
                query = query.where(
                    or_(
                        Employee.display_name.ilike(term, escape="\\"),
                        User.email.ilike(term, escape="\\"),
                    )
                )
            rows = self.session.execute(
                query.order_by(User.id).offset((page - 1) * 30).limit(31)
            ).all()
            return {"items": [person(row) for row in rows[:30]], "has_more": len(rows) > 30}

    def get_post(self, user: User, identifier: UUID) -> InternalPost:
        post = self.session.scalar(
            select(InternalPost).where(InternalPost.id == identifier, post_scope(user))
        )
        if post is None:
            raise ApiError(404, "post_not_found", "Post not found")
        return post

    def content_view(self, row: InternalPost | PostComment) -> dict[str, Any]:
        if row.author_id not in self.people:
            self.preload_content([row])
        data: dict[str, Any] = {
            "id": row.id,
            "author": self.people[row.author_id],
            "body": row.body,
            "created_at": row.created_at,
        }
        data["mentions"] = [
            self.people[UUID(value)] for value in row.mention_ids if UUID(value) in self.people
        ]
        if isinstance(row, InternalPost):
            data.update(
                title=row.title,
                department_id=row.department_id,
                department=self.departments.get(row.department_id) if row.department_id else None,
            )
        return data

    def feed(self, user: User, page: int, audience: str) -> dict[str, Any]:
        with self.session.begin():
            query = select(InternalPost).where(post_scope(user))
            if audience == "company":
                query = query.where(InternalPost.department_id.is_(None))
            elif audience == "department":
                query = query.where(InternalPost.department_id == department_of(user.id))
            rows = list(
                self.session.scalars(
                    query.order_by(InternalPost.created_at.desc(), InternalPost.id.desc())
                    .offset((page - 1) * 20)
                    .limit(21)
                )
            )
            own_department = self.session.scalar(select(department_of(user.id)))
            self.preload_content(list(rows[:20]))
            departments = self.session.execute(
                select(Department.id, Department.name)
                .where(
                    Department.is_active.is_(True),
                    true()
                    if user.role in (UserRole.HR, UserRole.ADMIN)
                    else Department.id == own_department,
                )
                .order_by(Department.name)
            ).all()
            return {
                "items": [self.content_view(row) for row in rows[:20]],
                "has_more": len(rows) > 20,
                "department_id": own_department,
                "can_publish_company": user.role in (UserRole.HR, UserRole.ADMIN),
                "departments": [{"id": item.id, "name": item.name} for item in departments],
            }

    def detail(self, user: User, identifier: UUID, page: int) -> dict[str, Any]:
        with self.session.begin():
            post = self.get_post(user, identifier)
            rows = list(
                self.session.scalars(
                    select(PostComment)
                    .where(PostComment.post_id == identifier)
                    .order_by(PostComment.created_at.desc(), PostComment.id.desc())
                    .offset((page - 1) * 20)
                    .limit(21)
                )
            )
            self.preload_content([post, *rows[:20]])
            return {
                "post": self.content_view(post),
                "comments": [self.content_view(row) for row in reversed(rows[:20])],
                "has_more": len(rows) > 20,
            }

    def recipients(self, department_id: UUID | None) -> list[User]:
        query = select(User).outerjoin(Employee, Employee.user_id == User.id).where(available())
        if department_id:
            query = query.where(
                or_(
                    Employee.department_id == department_id,
                    User.role.in_((UserRole.HR, UserRole.ADMIN)),
                )
            )
        return list(self.session.scalars(query))

    def notify(
        self,
        actor: User,
        kind: str,
        identifier: UUID,
        recipients: list[User],
        request_id: str,
        *,
        post_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> None:
        event = AuditWriter().record(
            self.session, actor.id, kind, "collaboration", str(identifier), request_id, {}
        )
        for recipient in recipients:
            if recipient.id != actor.id:
                self.session.add(
                    Notification(
                        event_id=event.id,
                        recipient_id=recipient.id,
                        recipient_role=recipient.role.value,
                        kind=kind,
                        post_id=post_id,
                        message_id=message_id,
                    )
                )
        signal(self.session, {actor.id} | {recipient.id for recipient in recipients})

    def publish(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        data: ContentInput,
        request_id: str,
        post_id: UUID | None = None,
    ) -> dict[str, Any]:
        with self.session.begin():
            actor = authorize_domain_write(self.session, context, csrf, tuple(UserRole))
            if isinstance(data, PostInput):
                own = self.session.scalar(select(department_of(actor.id)))
                if data.department_id is None:
                    if actor.role not in (UserRole.HR, UserRole.ADMIN):
                        raise ApiError(403, "forbidden", "Only HR or ADMIN publish company news")
                elif actor.role not in (UserRole.HR, UserRole.ADMIN) and data.department_id != own:
                    raise ApiError(
                        403, "forbidden", "Publish department news in your own department"
                    )
                if data.department_id and not self.session.scalar(
                    select(Department.id).where(
                        Department.id == data.department_id, Department.is_active.is_(True)
                    )
                ):
                    raise ApiError(422, "department_unavailable", "Department unavailable")
                department_id = data.department_id
                row: InternalPost | PostComment = InternalPost(
                    id=data.id,
                    author_id=actor.id,
                    department_id=department_id,
                    title=data.title,
                    body=data.body,
                )
                kind = "collaboration.post"
                parent_id = data.id
            else:
                assert post_id is not None
                post = self.get_post(actor, post_id)
                department_id = post.department_id
                row = PostComment(id=data.id, post_id=post_id, author_id=actor.id, body=data.body)
                kind = "collaboration.comment"
                parent_id = post_id
            recipients = self.recipients(department_id)
            valid_ids = {user.id for user in recipients}
            if set(data.mentions) - valid_ids:
                raise ApiError(422, "invalid_mention", "Mentioned people must be in the audience")
            # Client UUID makes a retry safe: never create duplicate messages/notifications.
            row.mention_ids = sorted(str(value) for value in set(data.mentions))
            existing = cast(InternalPost | PostComment | None, self.session.get(type(row), data.id))
            if existing is not None:
                if (
                    existing.author_id != actor.id
                    or existing.mention_ids != row.mention_ids
                    or existing.body != row.body
                    or (
                        isinstance(existing, InternalPost)
                        and isinstance(row, InternalPost)
                        and (
                            existing.title != row.title
                            or existing.department_id != row.department_id
                        )
                    )
                    or (
                        isinstance(existing, PostComment)
                        and isinstance(row, PostComment)
                        and existing.post_id != row.post_id
                    )
                ):
                    raise ApiError(409, "id_conflict", "Content identifier already used")
                return self.content_view(existing)
            self.session.add(row)
            self.session.flush()
            if kind == "collaboration.post":
                targets = recipients
            else:
                targets = [
                    user for user in recipients if user.id in set(data.mentions) | {post.author_id}
                ]
            self.notify(actor, kind, row.id, targets, request_id, post_id=parent_id)
            # Feed refresh reaches the audience without creating a notice for every comment.
            signal(self.session, valid_ids)
            return self.content_view(row)

    def messages(self, user: User, peer_id: UUID, before: UUID | None) -> dict[str, Any]:
        with self.session.begin():
            pair = or_(
                and_(ChatMessage.sender_id == user.id, ChatMessage.recipient_id == peer_id),
                and_(ChatMessage.sender_id == peer_id, ChatMessage.recipient_id == user.id),
            )
            query = select(ChatMessage).where(pair)
            if before:
                cursor = self.session.scalar(
                    select(ChatMessage).where(pair, ChatMessage.id == before)
                )
                if cursor is None:
                    raise ApiError(404, "message_not_found", "Message not found")
                query = query.where(
                    tuple_(ChatMessage.created_at, ChatMessage.id)
                    < tuple_(cursor.created_at, cursor.id)
                )
            rows = list(
                self.session.scalars(
                    query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(31)
                )
            )
            return {
                "items": [self.message_view(row) for row in reversed(rows[:30])],
                "has_more": len(rows) > 30,
            }

    @staticmethod
    def message_view(row: ChatMessage) -> dict[str, Any]:
        return {
            "id": row.id,
            "sender_id": row.sender_id,
            "recipient_id": row.recipient_id,
            "body": row.body,
            "created_at": row.created_at,
            "read_at": row.read_at,
        }

    def send(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        peer_id: UUID,
        data: ContentInput,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            actor = authorize_domain_write(self.session, context, csrf, tuple(UserRole), {peer_id})
            peer = self.session.scalar(
                select(User)
                .outerjoin(Employee, Employee.user_id == User.id)
                .where(User.id == peer_id, User.id != actor.id, available())
            )
            if peer is None:
                raise ApiError(404, "recipient_not_found", "Recipient unavailable")
            if set(data.mentions) - {peer_id}:
                raise ApiError(
                    422, "invalid_mention", "A private chat can only mention its recipient"
                )
            existing = self.session.get(ChatMessage, data.id)
            if existing:
                if (
                    existing.sender_id != actor.id
                    or existing.recipient_id != peer_id
                    or existing.body != data.body
                ):
                    raise ApiError(409, "id_conflict", "Message identifier already used")
                return self.message_view(existing)
            row = ChatMessage(id=data.id, sender_id=actor.id, recipient_id=peer_id, body=data.body)
            self.session.add(row)
            self.session.flush()
            self.notify(
                actor,
                "collaboration.mention" if data.mentions else "collaboration.message",
                row.id,
                [peer],
                request_id,
                message_id=row.id,
            )
            return self.message_view(row)

    def conversations(self, user: User, page: int) -> dict[str, Any]:
        with self.session.begin():
            peer = case(
                (ChatMessage.sender_id == user.id, ChatMessage.recipient_id),
                else_=ChatMessage.sender_id,
            )
            ranked = (
                select(
                    ChatMessage.id.label("id"),
                    peer.label("peer_id"),
                    func.row_number()
                    .over(
                        partition_by=peer,
                        order_by=(ChatMessage.created_at.desc(), ChatMessage.id.desc()),
                    )
                    .label("rank"),
                )
                .where(or_(ChatMessage.sender_id == user.id, ChatMessage.recipient_id == user.id))
                .subquery()
            )
            rows = self.session.execute(
                select(ChatMessage, ranked.c.peer_id)
                .join(ranked, ranked.c.id == ChatMessage.id)
                .where(ranked.c.rank == 1)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .offset((page - 1) * 20)
                .limit(21)
            ).all()
            unread = (
                self.session.scalar(
                    select(func.count())
                    .select_from(ChatMessage)
                    .where(ChatMessage.recipient_id == user.id, ChatMessage.read_at.is_(None))
                )
                or 0
            )
            contacts = {
                row[0].id: person(row)
                for row in self.session.execute(
                    self.people_query().where(User.id.in_([peer_id for _, peer_id in rows[:20]]))
                )
            }
            items = []
            for row, peer_id in rows[:20]:
                items.append({"peer": contacts[peer_id], "latest": self.message_view(row)})
            return {"items": items, "has_more": len(rows) > 20, "unread_count": unread}

    def read(self, context: AuthContext, csrf: CsrfCheck, peer_id: UUID, through: UUID) -> None:
        with self.session.begin():
            actor = authorize_domain_write(self.session, context, csrf, tuple(UserRole), {peer_id})
            last = self.session.scalar(
                select(ChatMessage).where(
                    ChatMessage.id == through,
                    ChatMessage.recipient_id == actor.id,
                    ChatMessage.sender_id == peer_id,
                )
            )
            if last is None:
                raise ApiError(404, "message_not_found", "Message not found")
            ids = select(ChatMessage.id).where(
                ChatMessage.sender_id == peer_id,
                ChatMessage.recipient_id == actor.id,
                tuple_(ChatMessage.created_at, ChatMessage.id) <= tuple_(last.created_at, last.id),
            )
            self.session.execute(
                update(Notification)
                .where(
                    Notification.recipient_id == actor.id,
                    Notification.message_id.in_(ids),
                    Notification.read_at.is_(None),
                )
                .values(read_at=datetime.now(UTC))
            )
            self.session.execute(
                update(ChatMessage)
                .where(ChatMessage.id.in_(ids), ChatMessage.read_at.is_(None))
                .values(read_at=datetime.now(UTC))
            )
            signal(self.session, {actor.id, peer_id})
