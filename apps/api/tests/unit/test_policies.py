from uuid import uuid4

import pytest

from app.core.errors import ApiError
from app.core.policies import AuthContext, require_roles
from app.modules.auth.models import AuthSession
from app.modules.users.models import User, UserRole


@pytest.mark.parametrize("role", list(UserRole))
def test_role_dependency_uses_current_role_and_does_not_grant_admin_hr_access(role):
    user = User(id=uuid4(), email="role@example.com", role=role, is_active=True)
    context = AuthContext(user=user, family_id=uuid4(), session=AuthSession())
    allow_hr = require_roles(UserRole.HR)
    if role == UserRole.HR:
        assert allow_hr(context) is context
    else:
        with pytest.raises(ApiError) as failure:
            allow_hr(context)
        assert failure.value.status_code == 403
        assert failure.value.code == "forbidden"


def test_multiple_allowed_roles_and_current_role_change():
    user = User(role=UserRole.MANAGER)
    context = AuthContext(user=user, family_id=uuid4(), session=AuthSession())
    policy = require_roles(UserRole.ADMIN, UserRole.MANAGER)
    assert policy(context) is context
    user.role = UserRole.EMPLOYEE
    with pytest.raises(ApiError, match="forbidden"):
        policy(context)
