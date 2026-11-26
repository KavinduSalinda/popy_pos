"""Groq chat completions. The API key is never written into the prompt."""

import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from apps.insights.models import ShopInsightSettings
from apps.insights.services import model_facts, prediction_fallback

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SUMMARY_SYSTEM = (
    "You are a shop assistant. Use only the JSON facts. Do not invent quantities. "
    "These figures are estimates from the last 30 days of sales. "
    "If the facts do not contain an answer, say so. "
    "Write plain sentences a shop owner can read aloud. "
    "No markdown, no asterisks, no headings, no bullet symbols, and no JSON field names. "
    "Do not add a currency symbol. "
    'Reply with JSON only: {"summary":"two short sentences on recent trading",'
    '"prediction":"three short sentences on what to buy for 7, 30, and 90 days"}'
)

ASK_SYSTEM = (
    "You help one shop owner. Use only the JSON facts. Do not invent quantities. "
    "Call the figures estimates from the last 30 days of sales. "
    "If the facts do not contain the answer, say so. "
    "Answer in short sentences, at most six lines, with a blank line between lines. "
    "No markdown, no asterisks, no headings, no numbered lists, and no bullet symbols. "
    "Never mention field names such as buy90, need30, or per_day. "
    "Say the idea in words, for example: buy 30 units over 90 days. "
    "Do not show formulas. Do not add a currency symbol. "
    "If the user only says hello, reply with one friendly sentence. "
    "Never answer with braces or JSON."
)


class InsightsError(Exception):
    def __init__(self, message: str, status: int, code: str):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def resolve_api_key(shop) -> str:
    row = ShopInsightSettings.objects.filter(shop=shop).first()
    if row and row.groq_api_key.strip():
        return row.groq_api_key.strip()
    return (getattr(settings, "GROQ_API_KEY", "") or "").strip()


def key_hint(key: str) -> str:
    if len(key) < 4:
        return ""
    return f"••••{key[-4:]}"


def _groq_model() -> str:
    return (getattr(settings, "GROQ_MODEL", "") or "").strip() or "openai/gpt-oss-120b"


def _message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or ""))
        joined = "\n".join(part.strip() for part in parts if part and part.strip())
        if joined:
            return joined
    reasoning = message.get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return ""


def _provider_message(exc: HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        message = data.get("error", {}).get("message") if isinstance(data, dict) else ""
        message = message or raw
    except json.JSONDecodeError:
        message = raw if "raw" in locals() else ""
    except Exception:
        message = ""
    message = " ".join(str(message).split())
    if "1010" in message:
        return "Groq blocked this server's request. Try again in a moment."
    if len(message) > 180:
        message = message[:180].rstrip() + "…"
    return message or "The insights service could not write a reply. Try again."


def _complete(api_key: str, messages: list[dict]) -> str:
    payload = {
        "model": _groq_model(),
        "messages": messages,
        "max_completion_tokens": 2048,
        "reasoning_effort": "low",
    }
    request = Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PopyPOS/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        logger.warning("Groq request failed with HTTP %s", exc.code)
        if exc.code == 429:
            raise InsightsError(
                "Groq is busy on the free plan. Wait a moment and try again.",
                429,
                "AI_RATE_LIMITED",
            ) from exc
        raise InsightsError(_provider_message(exc), 502, "AI_UNAVAILABLE") from exc
    except URLError as exc:
        logger.warning("Groq request could not connect: %s", exc.reason)
        raise InsightsError(
            "The insights service is unreachable. Check the internet connection.",
            503,
            "AI_UNAVAILABLE",
        ) from exc
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        logger.warning("Groq returned an unexpected payload")
        raise InsightsError(
            "The insights service could not write a reply. Try again.",
            502,
            "AI_UNAVAILABLE",
        ) from None

    try:
        text = _message_text(body["choices"][0]["message"])
    except (KeyError, IndexError, TypeError):
        text = ""
    if not text:
        raise InsightsError(
            "The insights service could not write a reply. Try again.",
            502,
            "AI_UNAVAILABLE",
        )
    return text


def _require_key(shop) -> str:
    key = resolve_api_key(shop)
    if not key:
        raise InsightsError(
            "Add a free Groq API key to write insights.",
            400,
            "AI_NOT_CONFIGURED",
        )
    return key


def _facts_message(shop) -> str:
    return "Facts:\n" + json.dumps(model_facts(shop), ensure_ascii=False)


def plain_reply(text: str) -> str:
    """Turn a model reply into short plain lines, without markdown or field names."""
    cleaned = text.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ")
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.M)
    cleaned = re.sub(r"\*\*|__|`", "", cleaned)
    cleaned = re.sub(
        r"\s*\((?:the\s+)?[\"“”']?(?:buy90|buy30|buy7|need90|need30|need7|per_day)[\"“”']?(?:\s+figure)?\)",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\b(?:buy90|buy30|buy7|need90|need30|need7|per_day)\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", cleaned, flags=re.M)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()
    if re.fullmatch(r"[\s{}\[\]]*", cleaned):
        return ""
    return cleaned


def _parse_writing(text: str) -> tuple[str, str]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            summary = str(data.get("summary") or "").strip()
            prediction = str(data.get("prediction") or "").strip()
            if summary or prediction:
                return summary, prediction
    return raw, ""


def write_summary(shop) -> dict:
    key = _require_key(shop)
    facts = model_facts(shop)
    text = _complete(
        key,
        [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": "Facts:\n" + json.dumps(facts, ensure_ascii=False)},
        ],
    )
    summary, prediction = _parse_writing(text)
    summary = plain_reply(summary)
    prediction = plain_reply(prediction)
    if not prediction:
        prediction = prediction_fallback(facts)
    if not summary:
        summary = "Recent trading is included in the facts for this shop."
    return {"summary": summary, "prediction": prediction}


def answer_question(shop, question: str, history: list[dict]) -> str:
    key = _require_key(shop)
    messages = [
        {"role": "system", "content": ASK_SYSTEM + "\n" + _facts_message(shop)},
    ]
    for turn in history[-6:]:
        messages.append({"role": turn["role"], "content": str(turn["content"])[:1000]})
    messages.append({"role": "user", "content": question[:500]})
    reply = plain_reply(_complete(key, messages))
    if not reply:
        return "Hello. Ask what to buy for the next 7, 30, or 90 days."
    return reply
