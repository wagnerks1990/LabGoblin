from pydantic import BaseModel, Field, SecretStr


class TemplateCredentialWrite(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=4096)
    domain: str = Field(default="", max_length=128)
    auto_connect: bool = True
    student_visible: bool = False


class TemplateCredentialPolicy(BaseModel):
    auto_connect: bool
    student_visible: bool


class TemplateCredentialStatus(TemplateCredentialPolicy):
    configured: bool


class GuestCredentialReveal(BaseModel):
    username: str
    password: str
    domain: str
    source: str = "template"
