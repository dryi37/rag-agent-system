from pydantic import BaseModel, EmailStr

# Thread
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str


# Auth
class ThreadResponse(BaseModel):
    thread_id: str

class MessageRequest(BaseModel):
    query: str
    skip_cache: bool = False
