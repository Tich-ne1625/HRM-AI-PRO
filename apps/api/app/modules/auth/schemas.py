from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.modules.users.models import UserRole


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class LoginCommand(BaseModel):
    email: str
    password: SecretStr
    request_id: str


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: UserRole
    is_active: bool
    employee_id: UUID | None = None


class ChangePasswordRequest(BaseModel):
    old_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=12, max_length=128)
