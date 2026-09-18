from pydantic import BaseModel, EmailStr, Field

from app.schemas.password import Password


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    full_name: str = Field(min_length=1, max_length=200)
    university: str | None = Field(default=None, max_length=200)
    program: str | None = Field(default=None, max_length=200)
    # A record, not a control. Nobody's age can be verified from here, and
    # bypassing the tick box gains an attacker nothing they could not get by
    # ticking it — so this is not security theatre dressed as validation. It
    # exists because the terms assert that a contract was accepted, and without
    # a stored acceptance there is no evidence any given account ever did, or of
    # which version they saw.
    accepted_terms: bool = Field(
        description="The registrant confirmed the age minimum and accepted the terms."
    )
    terms_version: str | None = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: Password


class VerifyEmailRequest(BaseModel):
    token: str


class DeleteAccountRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
