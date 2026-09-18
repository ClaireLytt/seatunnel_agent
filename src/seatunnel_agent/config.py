from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_VALID_PROVIDERS = ("anthropic", "openai")


@dataclass(frozen=True)
class Settings:
    api_key: str
    seatunnel_home: str = ""
    max_retries: int = 3
    model_name: str = "claude-opus-5"
    max_tokens: int = 16000
    seatunnel_bin: str = ""
    llm_provider: str = "anthropic"
    llm_base_url: str = ""
    job_timeout: int = 120
    temperature: float = 0.0
    config_dir: str = "configs"
    seatunnel_api_url: str = ""

    @property
    def anthropic_api_key(self) -> str:
        return self.api_key


def load_settings() -> Settings:
    load_dotenv()

    api_key = os.getenv("API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "API_KEY is not set. "
            "Copy .env.example to .env and fill in your API key."
        )

    llm_provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if llm_provider not in _VALID_PROVIDERS:
        raise RuntimeError(
            f"LLM_PROVIDER='{llm_provider}' is not supported. "
            f"Choose one of: {', '.join(_VALID_PROVIDERS)}"
        )

    seatunnel_home = os.getenv("SEATUNNEL_HOME", "")

    max_retries = int(os.getenv("MAX_RETRIES", "3"))
    model_name = os.getenv("MODEL_NAME", "claude-opus-5")
    max_tokens = int(os.getenv("MAX_TOKENS", "16000"))
    llm_base_url = os.getenv("LLM_BASE_URL", "")
    job_timeout = int(os.getenv("JOB_TIMEOUT", "120"))
    temperature = float(os.getenv("TEMPERATURE", "0.0"))
    config_dir = os.getenv("CONFIG_DIR", "configs")
    seatunnel_api_url = os.getenv("SEATUNNEL_API_URL", "")

    seatunnel_bin = ""
    if seatunnel_home:
        bin_name = "seatunnel.cmd" if platform.system() == "Windows" else "seatunnel.sh"
        seatunnel_bin = str(Path(seatunnel_home) / "bin" / bin_name)

        if not Path(seatunnel_bin).exists():
            from rich.console import Console
            Console(stderr=True).print(
                f"[yellow]Warning:[/yellow] SeaTunnel binary not found at {seatunnel_bin}. "
                "The 'run' command will fail, but 'validate' and 'diagnose' still work."
            )

    return Settings(
        api_key=api_key,
        seatunnel_home=seatunnel_home,
        max_retries=max_retries,
        model_name=model_name,
        max_tokens=max_tokens,
        seatunnel_bin=seatunnel_bin,
        llm_provider=llm_provider,
        llm_base_url=llm_base_url,
        job_timeout=job_timeout,
        temperature=temperature,
        config_dir=config_dir,
        seatunnel_api_url=seatunnel_api_url,
    )
