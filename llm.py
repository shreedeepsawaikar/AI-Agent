import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv(override=True)

DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_llm(temperature: float = 0.2, model: str | None = None) -> ChatOpenAI:
    """Return a ChatOpenAI client configured for OpenRouter."""
    load_dotenv(override=True)

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "Missing OpenRouter API key. Please add OPENROUTER_API_KEY to your .env file."
        )

    chosen_model = model or os.getenv("OPENROUTER_MODEL", "").strip()
    if not chosen_model or chosen_model in ["openrouter/free", "default"]:
        chosen_model = DEFAULT_OPENROUTER_MODEL

    base_url = os.getenv("OPENROUTER_BASE_URL", "").strip() or OPENROUTER_BASE_URL

    return ChatOpenAI(
        model=chosen_model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        default_headers={
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "AI Research Agent",
        },
    )
