# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 QuickCall

"""Application settings loaded from environment."""


import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:
    BaseSettings = None
    SettingsConfigDict = None


if BaseSettings is not None:

    class Settings(BaseSettings):
        openai_api_key: str = ""
        openai_base_url: str = "https://api.deepseek.com/v1"
        model: str = "deepseek-v4-pro"
        concurrency: int = 30
        temp_dir: str = "/tmp/standalone-trace-analyzer"

        model_config = SettingsConfigDict(env_prefix="", env_file=".env")

else:

    class Settings:
        def __init__(self) -> None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
            self.openai_base_url = os.getenv(
                "OPENAI_BASE_URL",
                "https://api.deepseek.com/v1",
            )
            self.model = os.getenv("MODEL", "deepseek-v4-pro")
            self.concurrency = int(os.getenv("CONCURRENCY", "30"))
            self.temp_dir = os.getenv("TEMP_DIR", "/tmp/standalone-trace-analyzer")


settings = Settings()
