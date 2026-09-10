import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", fallback_model: str = None):
        self.base_url = base_url
        self.session = requests.Session()
        self.timeout = 300
        # Used only if a generate() call times out. Configurable rather than
        # hardcoded so it actually matches whatever model you've configured
        # (OLLAMA_DEV_MODEL/OLLAMA_USER_MODEL) instead of assuming one
        # specific model name is always pulled.
        self.fallback_model = fallback_model or os.environ.get("OLLAMA_FALLBACK_MODEL", "qwen2.5-coder:7b")

    def health_check(self) -> bool:
        """Verify Ollama is running."""
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except:
            return False

    def list_models(self) -> list:
        """Get available models."""
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return [m["name"] for m in resp.json().get("models", [])]
        except:
            return []

    def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        context_length: int = 4096,
        top_p: float = 0.9
    ) -> str:
        """Generate text from prompt."""
        payload = {
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "num_ctx": context_length,
            "top_p": top_p,
            "stream": False,
        }
        
        try:
            logger.info(f"Generating with {model}...")
            resp = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except requests.Timeout:
            logger.warning(f"Timeout on {model}, retrying with fallback {self.fallback_model}...")
            if model != self.fallback_model:
                return self.generate(
                    self.fallback_model, prompt,
                    temperature=temperature, context_length=context_length, top_p=top_p
                )
            raise
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    def ensure_model_loaded(self, model: str) -> bool:
        """Ensure model is available."""
        try:
            models = self.list_models()
            if model in models:
                return True
            logger.info(f"Pulling {model}...")
            resp = self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model},
                timeout=600
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to load {model}: {e}")
            return False
