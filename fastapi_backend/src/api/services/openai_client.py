import os
from typing import Any, Dict, Optional

import httpx


OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# PUBLIC_INTERFACE
def analyze_contract_text_with_openai(
    text: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout_seconds: int = 60,
) -> Dict[str, Any]:
    """Send extracted contract text to OpenAI for analysis.

    This function calls OpenAI's Chat Completions API to extract key insights
    from the provided contract text. It uses the OPENAI_API_KEY environment
    variable unless an api_key is explicitly provided.

    Args:
        text: The contract text extracted from the PDF.
        api_key: Optional override for the OpenAI API key; defaults to env var.
        model: Optional override for model name; defaults to OPENAI_MODEL or a sane default.
        timeout_seconds: HTTP timeout for the API call.

    Returns:
        A dict containing the parsed JSON-like insights and raw response.

    Raises:
        RuntimeError: If the API key is missing or OpenAI API returns an error.
    """
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    mdl = model or DEFAULT_OPENAI_MODEL

    # Compose a system and user message to guide extraction
    system_prompt = (
        "You are an assistant that extracts structured insights from legal contracts. "
        "Return a concise JSON object with keys: parties, effective_date, termination_date, "
        "payment_terms, renewal_terms, governing_law, obligations, termination_clauses, "
        "deadlines, risks. Keep values as short strings or arrays of strings. "
        "If unknown, use null."
    )
    user_prompt = (
        "Extract the requested fields from the following contract text.\n\n"
        f"{text[:20000]}"  # limit payload to avoid excessive token usage
    )

    url = f"{OPENAI_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": mdl,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
    except Exception as exc:
        raise RuntimeError(f"Failed to call OpenAI API: {exc}") from exc

    if resp.status_code >= 400:
        raise RuntimeError(
            f"OpenAI API error {resp.status_code}: {resp.text[:500]}"
        )

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        content = None

    return {"insights": content, "raw": data}
