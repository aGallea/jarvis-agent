from pydantic import Field, BaseSettings


class Settings(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    log_level: str = Field(default="INFO")
