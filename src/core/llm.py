# ==============================================================================
# File Location: dart-agent/src/core/llm.py
# File Name: llm.py
# Description:
# - LLM wrapper for Gemini with config-driven model selection and retry/backoff.
# - Structured as a client class so agents can have persona-specific instances later.
# Inputs:
# - Prompts from agents; model/api settings from config; Google API credentials.
# Outputs:
# - Generated text responses or sanitized error strings.
# ==============================================================================

import time
import google.generativeai as genai
from google.api_core import exceptions
from src.utils.config import config

if not config.google_api_key:
    print("⚠️ WARNING: GOOGLE_API_KEY not found in configuration.")

try:
    genai.configure(api_key=config.google_api_key)
except Exception as e:
    print(f"⚠️ Error configuring Gemini: {e}")


class LLMClient:
    """
    Thin wrapper around Gemini with retry/backoff.
    Structured so we can later add persona/instructions/tools per agent.
    """

    def __init__(self, model_name: str, temperature: float, max_tokens: int, retries: int = 3):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.retries = retries
        self._model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            },
        )

    def generate(self, prompt: str) -> str:
        for attempt in range(self.retries):
            try:
                response = self._model.generate_content(prompt)
                return response.text
            except exceptions.ResourceExhausted:
                wait_time = 2 ** attempt
                if attempt < self.retries - 1:
                    print(f"   ⚠️ LLM Rate Limit hit. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    return "LLM_ERROR: Quota Exceeded (429). Please wait a moment."
            except Exception as e:
                print(f"   ⚠️ LLM Exception Details: {repr(e)}")
                raw_error = str(e).strip() or repr(e)
                error_msg = raw_error.split('\n')[0].strip()
                if not error_msg:
                    return "LLM_ERROR: Unknown API Error (Blank error message)"
                if "429" in error_msg:
                    return "LLM_ERROR: Quota Exceeded (429). Please wait a moment."
                if "503" in error_msg:
                    return "LLM_ERROR: Service Unavailable (503). Retry shortly."
                return f"LLM_ERROR: {error_msg}"

        return "LLM_ERROR: Unknown Failure (Max retries exceeded)"


# Default client shared by agents (persona-specific clients can be added later)
_default_client = LLMClient(
    model_name=config.model_name,
    temperature=config.temperature,
    max_tokens=config.max_tokens,
    retries=3,
)


def call_model(prompt: str, retries: int = None) -> str:
    """
    Backward-compatible entrypoint. Uses default client for now.
    """
    client = _default_client
    if retries is not None and retries != client.retries:
        client = LLMClient(
            model_name=config.model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            retries=retries,
        )
    return client.generate(prompt)
