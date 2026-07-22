from functools import lru_cache
from pathlib import Path

PROMPT_DIRECTORY = Path(__file__).parent


@lru_cache
def load_prompt(name: str) -> str:
    """Load a version-controlled agent prompt and reject unsafe or empty names."""
    if not name or not name.replace("_", "").isalnum():
        raise ValueError(f"Invalid agent prompt name: {name!r}")
    prompt = (PROMPT_DIRECTORY / f"{name}.md").read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"Agent prompt is empty: {name}")
    return prompt


__all__ = ["PROMPT_DIRECTORY", "load_prompt"]
