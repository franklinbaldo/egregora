"""Avatar generation tools."""

import hashlib
import importlib.resources
import yaml
from functools import lru_cache

@lru_cache(maxsize=1)
def _get_avatar_data() -> dict[str, list[str]]:
    """Load avatar data from YAML, caching it for performance."""
    with importlib.resources.open_text("egregora.resources", "avatars.yml") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise TypeError("Avatar data must be a dictionary.")
    return data


def generate_fallback_avatar_url(author_uuid: str) -> str:
    """Generate a deterministic fallback avatar URL using avataaars.io.

    Args:
        author_uuid: The author's UUID
    Returns:
        A URL to a generated avatar image.

    """
    avatar_data = _get_avatar_data()

    # Deterministically select options based on UUID hash
    h = hashlib.sha256(author_uuid.encode()).hexdigest()

    # Helper to pick from options
    def pick(options_key: str, offset: int) -> str:
        options = avatar_data[options_key]
        idx = int(h[offset : offset + 2], 16) % len(options)
        return options[idx]

    params = [
        f"accessoriesType={pick('accessories', 0)}",
        "avatarStyle=Circle",
        f"clotheType={pick('clothes', 2)}",
        f"eyeType={pick('eyes', 4)}",
        f"eyebrowType={pick('eyebrows', 6)}",
        "facialHairType=Blank",
        f"hairColor={pick('hair_colors', 8)}",
        f"mouthType={pick('mouths', 10)}",
        f"skinColor={pick('skin_colors', 12)}",
        f"topType={pick('tops', 14)}",
    ]

    return f"https://avataaars.io/?{'&'.join(params)}"
