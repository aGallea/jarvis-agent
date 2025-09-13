from pydantic import Field, BaseSettings


class Settings(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    log_level: str = Field(default="INFO")
    jarvis_app_url: str = Field(default="ws://localhost:8001/ws")
    backend_direct_access: bool = Field(default=True)
    backend_url: str = Field(default="http://localhost:8002")
