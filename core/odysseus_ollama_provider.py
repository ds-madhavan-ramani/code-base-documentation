"""Custom Ollama provider for Odysseus Harness.

Replaces the default Gemini provider to use local Ollama models.
This allows Odysseus to run entirely offline using open-source models.
"""

import json
import logging
import os
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# Default to Qwen (strong reasoning capabilities)
DEFAULT_MODEL = os.environ.get("ODYSSEUS_MODEL", "qwen2.5-coder:32b")
OLLAMA_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")


def api_key() -> str:
    """Ollama doesn't require API keys - just return a placeholder."""
    return "local-ollama"


def complete(model: str, system: str, messages: list[dict], tools: list[dict]) -> dict:
    """
    One model call using Ollama.

    Returns: {"text": str, "tool_calls": [...], "usage": {...}}

    This mimics Odysseus's expected interface but uses Ollama's REST API.
    """
    model = model or DEFAULT_MODEL

    try:
        # Build the prompt
        prompt = _build_prompt(system, messages, tools)

        # Call Ollama
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.7,  # Good for reasoning
            },
            timeout=600,  # 10 minutes
        )
        response.raise_for_status()

        result = response.json()
        text = result.get("response", "")

        # Try to extract tool calls if tools were provided
        tool_calls = []
        if tools:
            tool_calls = _extract_tool_calls(text, tools)

        return {
            "text": text,
            "tool_calls": tool_calls,
            "usage": {
                "input": result.get("prompt_eval_count", 0),
                "output": result.get("eval_count", 0),
            },
        }

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot connect to Ollama at {OLLAMA_URL}")
        logger.error("Make sure Ollama is running: ollama serve")
        raise RuntimeError(
            f"Ollama not responding at {OLLAMA_URL}. "
            "Start Ollama with: ollama serve"
        ) from e
    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        raise RuntimeError(f"Ollama analysis failed: {e}") from e


def _build_prompt(system: str, messages: list[dict], tools: list[dict]) -> str:
    """Build a prompt from system, messages, and tools."""
    prompt = f"{system}\n\n"

    for msg in messages:
        if msg["role"] == "user":
            prompt += f"User: {msg['text']}\n\n"
        elif msg["role"] == "assistant":
            prompt += f"Assistant: {msg['text']}\n\n"
        elif msg["role"] == "tool":
            prompt += f"Tool {msg.get('name', 'unknown')}: {msg['text']}\n\n"

    # Add tools if provided
    if tools:
        prompt += "Available tools:\n"
        for tool in tools:
            schema = tool.get("schema", {})
            prompt += f"- {schema.get('name', 'unknown')}: {schema.get('description', '')}\n"
        prompt += "\nRespond with tool calls in JSON format if needed.\n"

    prompt += "Assistant: "
    return prompt


def _extract_tool_calls(text: str, tools: list[dict]) -> list[dict]:
    """Try to extract tool calls from model response.

    Looks for JSON tool calls in the response.
    """
    tool_calls = []

    # Try to find JSON in the response
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = text[start:end]
            call_data = json.loads(json_str)

            # Check if it looks like a tool call
            if isinstance(call_data, dict):
                if "name" in call_data and "args" in call_data:
                    tool_calls.append(call_data)
    except (json.JSONDecodeError, ValueError):
        pass

    return tool_calls


def list_available_models() -> list[str]:
    """Get list of available models from Ollama."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        response.raise_for_status()
        models = response.json().get("models", [])
        return [m["name"] for m in models]
    except Exception as e:
        logger.warning(f"Failed to list Ollama models: {e}")
        return []


def health_check() -> bool:
    """Check if Ollama is running."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False
