"""LLM Client - Unified LLM interface supporting multiple providers."""

import os
import json
from typing import Optional
from openai import OpenAI
import yaml


class LLMClient:
    """Unified LLM client wrapper supporting Agnes AI, OpenAI, Anthropic etc."""

    def __init__(self, config_path: Optional[str] = None):
        self._config = self._load_config(config_path)
        self._clients = {}
        self._setup_clients()

    def _load_config(self, config_path: Optional[str]):
        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml"
        )
        if os.path.exists(default_path):
            with open(default_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _get_config(self):
        return self._config.get("llm", {})

    def _setup_clients(self):
        llm_cfg = self._get_config()
        provider = llm_cfg.get("provider", "agnes")
        api_key = llm_cfg.get("api_key", os.environ.get("AGNES_API_KEY", ""))
        base_url = llm_cfg.get("base_url", "https://apihub.agnes-ai.com/v1")

        if provider == "agnes" or provider == "openai":
            self._clients["default"] = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )
        elif provider == "anthropic":
            self._clients["default"] = OpenAI(
                api_key=api_key,
                base_url="https://api.anthropic.com/v1",
            )

    @property
    def default_model(self) -> str:
        return self._get_config().get("model", "agnes-2.0-flash")

    @property
    def default_temperature(self) -> float:
        return self._get_config().get("temperature", 0.85)

    @property
    def default_max_tokens(self) -> int:
        return self._get_config().get("max_tokens", 8192)

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send a chat completion request and return the response text."""
        client = self._clients.get("default")
        if not client:
            raise RuntimeError("No LLM client configured. Check config.yaml or env AGNES_API_KEY")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature if temperature is not None else self.default_temperature,
            max_tokens=max_tokens or self.default_max_tokens,
        )
        return response.choices[0].message.content

    def chat_structured(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_format: dict = {"type": "json_object"},
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> dict:
        """Send a chat request expecting JSON response."""
        text = self.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
        )
        return json.loads(text)

    def generate_script(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """Generate script content with script-specific settings."""
        script_cfg = self._get_config().get("script_model", self.default_model)
        script_temp = self._get_config().get("script_temperature", 0.9)
        return self.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            model=script_cfg,
            temperature=script_temp,
        )

    def generate_analysis(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """Generate analysis content with analysis-specific settings."""
        analysis_cfg = self._get_config().get("analysis_model", self.default_model)
        analysis_temp = self._get_config().get("analysis_temperature", 0.3)
        return self.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            model=analysis_cfg,
            temperature=analysis_temp,
        )
