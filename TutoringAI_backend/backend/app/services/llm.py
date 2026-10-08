import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
_client = None


def get_client() -> OpenAI:
    """Create the LLM client once and reuse it."""
    global _client
    if _client is None:
        key = os.getenv("LLM_API_KEY")
        if not key:
            raise RuntimeError("LLM_API_KEY is not configured")
        _client = OpenAI(
            api_key=key,
            base_url=os.getenv("LLM_BASE_URL") or None,
            timeout=30,
        )
    return _client

def chat(system: str, user: str, temperature: float = 0.2) -> str:
    """Send one system+user message and return the reply text."""
    resp = get_client().chat.completions.create(
        model=os.getenv("LLM_MODEL"),
        messages=[
               {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()