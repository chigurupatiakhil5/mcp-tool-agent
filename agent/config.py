from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Config specific to the agent client, kept separate from
    app/config.py's Settings. If GROQ_API_KEY lived on the shared Settings
    class instead, the FastAPI app (which never uses Groq) would fail to
    start without a Groq key just because it shares that class - these are
    two different components and shouldn't share a required-config surface
    just because they currently share one .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str


settings = AgentSettings()
