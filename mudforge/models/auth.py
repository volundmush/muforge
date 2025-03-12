import pydantic
import mudforge
import jwt
import uuid

from datetime import datetime, timedelta, timezone

class UserLogin(pydantic.BaseModel):
    email: pydantic.EmailStr
    password: pydantic.SecretStr

def _create_token(sub: str, expires: datetime, refresh: bool = False):
    data = {
        "sub": sub,
        "exp": expires,
        "iat": datetime.now(tz=timezone.utc),
    }
    if refresh:
        data["refresh"] = True
    jwt_settings = mudforge.SETTINGS["JWT"]
    return jwt.encode(data, jwt_settings["secret"], algorithm=jwt_settings["algorithm"])


def create_token(sub: str):
    jwt_settings = mudforge.SETTINGS["JWT"]
    return _create_token(
        sub,
        datetime.now(tz=timezone.utc)
        + timedelta(minutes=jwt_settings["token_expire_minutes"]),
    )


def create_refresh(sub: str):
    jwt_settings = mudforge.SETTINGS["JWT"]
    return _create_token(
        sub,
        datetime.now(tz=timezone.utc)
        + timedelta(minutes=jwt_settings["refresh_expire_minutes"]),
        True,
    )


class TokenResponse(pydantic.BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    @classmethod
    def from_uuid(cls, id: uuid.UUID) -> "TokenResponse":
        sub = str(id)
        token = create_token(sub)
        refresh = create_refresh(sub)
        return cls(access_token=token, refresh_token=refresh, token_type="bearer")


class RefreshTokenModel(pydantic.BaseModel):
    refresh_token: str