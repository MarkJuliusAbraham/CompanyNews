from pydantic import BaseModel, ConfigDict, Field


class SignIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, str_to_lower=True)

    username: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
