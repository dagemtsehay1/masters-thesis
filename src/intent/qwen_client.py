"""Optional local-LLM intent fallback via Ollama's HTTP API.

Only reached when the deterministic alias/fuzzy tiers can't resolve a
transcript (see IntentEngine). Deliberately bounded and defensive: a short
fixed prompt, deterministic decoding, a hard timeout with limited retries,
strict JSON-schema validation of the response, and an English-only default
scope. If Ollama is unreachable or the model returns junk, this returns
"unresolved" rather than ever raising into the pipeline - the fallback tier
being down must never break basic voice operation.

Uses only the Python standard library's urllib so no HTTP client dependency
is added for a single localhost endpoint.
"""
import json
import logging
import urllib.error
import urllib.request
from typing import Optional, Tuple

from pydantic import ValidationError

from src.config.schema import QwenConfig
from src.intent.schemas import QwenResponse, to_canonical

logger = logging.getLogger("intent.qwen")

_SYSTEM_PROMPT = (
    "You translate a short robot voice command into strict JSON. "
    'Respond with ONLY a JSON object of the form '
    '{"action": <"move"|"turn"|"stop">, "direction": <"forward"|"left"|"right"|"around"|null>, '
    '"speed": null, "duration": null, "confidence": <0..1>, "reason": <short string>}. '
    "Use action \"move\" with direction \"forward\" to go forward, action \"turn\" with a "
    "direction to rotate, and action \"stop\" with null direction to stop. "
    "Do not include any text outside the JSON."
)


class QwenClient:
    def __init__(self, config: QwenConfig):
        self.config = config
        self.enabled = config.enabled

    def health_check(self) -> bool:
        """Best-effort check that Ollama is reachable. Never raises."""
        try:
            request = urllib.request.Request(f"{self.config.url}/api/tags", method="GET")
            with urllib.request.urlopen(request, timeout=self.config.timeout_s) as response:
                return response.status == 200
        except Exception as exc:
            logger.info("Ollama health check failed: %s", exc)
            return False

    def resolve(self, normalized_text: str, language: str = "en") -> Tuple[Optional[str], float]:
        """Returns (canonical_command, confidence), or (None, 0.0). Only
        used as IntentEngine's last tier."""
        if not self.enabled:
            return None, 0.0
        if language not in self.config.languages:
            # Amharic (and any non-configured language) is intentionally not
            # routed to Qwen in the first iteration - alias/fuzzy only.
            return None, 0.0

        raw = self._call_with_retries(normalized_text)
        if raw is None:
            return None, 0.0

        try:
            response = QwenResponse(**raw)
        except (ValidationError, TypeError) as exc:
            logger.info("Qwen returned a response that failed schema validation: %s", exc)
            return None, 0.0

        canonical = to_canonical(response)
        if canonical is None:
            logger.info("Qwen proposed an out-of-vocabulary command: %s/%s", response.action, response.direction)
            return None, 0.0

        return canonical, max(0.0, min(1.0, response.confidence))

    def _call_with_retries(self, text: str) -> Optional[dict]:
        for attempt in range(self.config.retries + 1):
            result = self._call_once(text)
            if result is not None:
                return result
            logger.debug("Qwen call attempt %d returned nothing", attempt + 1)
        return None

    def _call_once(self, text: str) -> Optional[dict]:
        payload = {
            "model": self.config.model,
            "prompt": f"{_SYSTEM_PROMPT}\n\nCommand: {text}\nJSON:",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.url}/api/generate", data=data, headers={"Content-Type": "application/json"}, method="POST"
        )

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_s) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.info("Qwen request failed: %s", exc)
            return None

        # Ollama's /api/generate returns the model text under "response".
        model_text = body.get("response", "")
        try:
            return json.loads(model_text)
        except (json.JSONDecodeError, TypeError):
            logger.info("Qwen response was not valid JSON: %r", model_text[:200])
            return None
