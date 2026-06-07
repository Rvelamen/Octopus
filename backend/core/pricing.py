"""Model pricing data for cost calculation."""



# Fallback pricing in USD per 1M tokens (used when DB has no pricing)
FALLBACK_PRICING: dict[str, dict] = {
    # Anthropic
    "claude-opus-4-7": {"input": 15.0, "output": 75.0, "cached_input": 1.50},
    "claude-opus-4-6": {"input": 15.0, "output": 75.0, "cached_input": 1.50},
    "claude-opus-4": {"input": 15.0, "output": 75.0, "cached_input": 1.50},
    "claude-sonnet-4-7": {"input": 3.0, "output": 15.0, "cached_input": 0.30},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cached_input": 0.30},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0, "cached_input": 0.30},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.0, "cached_input": 0.08},
    "claude-haiku-4": {"input": 0.80, "output": 4.0, "cached_input": 0.08},
    "claude-3-opus": {"input": 15.0, "output": 75.0, "cached_input": 1.50},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0, "cached_input": 0.30},
    "claude-3-haiku": {"input": 0.25, "output": 1.25, "cached_input": 0.025},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0, "cached_input": 0.30},
    "claude-3-5-haiku": {"input": 0.25, "output": 1.25, "cached_input": 0.025},
    # OpenAI
    "gpt-4o": {"input": 2.5, "output": 10.0, "cached_input": 1.25},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached_input": 0.075},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0, "cached_input": 5.0},
    "gpt-4": {"input": 30.0, "output": 60.0, "cached_input": 15.0},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50, "cached_input": 0.25},
    "o1": {"input": 15.0, "output": 60.0, "cached_input": 7.50},
    "o3-mini": {"input": 1.10, "output": 4.40, "cached_input": 0.55},
    "o4-mini": {"input": 1.10, "output": 4.40, "cached_input": 0.55},
    # DeepSeek
    "deepseek-chat": {"input": 0.27, "output": 1.10, "cached_input": 0.07},
    "deepseek-coder": {"input": 0.27, "output": 1.10, "cached_input": 0.07},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19, "cached_input": 0.14},
    # Google
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0, "cached_input": 0.3125},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60, "cached_input": 0.0375},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "cached_input": 0.025},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0, "cached_input": 0.3125},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "cached_input": 0.01875},
    # Grok
    "grok-3": {"input": 3.0, "output": 15.0, "cached_input": 0.75},
    "grok-3-mini": {"input": 0.30, "output": 0.50, "cached_input": 0.075},
    # Mistral
    "mistral-large": {"input": 2.0, "output": 6.0, "cached_input": 0.50},
    "mistral-medium": {"input": 2.70, "output": 8.10, "cached_input": 0.675},
    "mistral-small": {"input": 0.20, "output": 0.60, "cached_input": 0.05},
    # Cohere
    "command-r-plus": {"input": 3.0, "output": 15.0, "cached_input": 0.75},
    "command-r": {"input": 0.50, "output": 1.50, "cached_input": 0.125},
    # Default fallback
    "default": {"input": 3.0, "output": 12.0, "cached_input": 0.75},
}


def get_fallback_pricing(model_id: str) -> dict:
    """Get fallback pricing for a model ID from hardcoded table."""
    if model_id in FALLBACK_PRICING:
        return FALLBACK_PRICING[model_id]
    for key in sorted(FALLBACK_PRICING.keys(), key=len, reverse=True):
        if key != "default" and model_id.startswith(key):
            return FALLBACK_PRICING[key]
    for key in sorted(FALLBACK_PRICING.keys(), key=len, reverse=True):
        if key != "default" and key in model_id:
            return FALLBACK_PRICING[key]
    return FALLBACK_PRICING["default"]


def calculate_cost(
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    cache_creation_tokens: int = 0,
    db_pricing: dict | None = None,
) -> float:
    """Calculate cost in USD for a given token usage.

    Args:
        model_id: The model identifier
        prompt_tokens: Total prompt/input tokens (including cached)
        completion_tokens: Output/completion tokens
        cached_tokens: Cache hit tokens (read from cache)
        cache_creation_tokens: Cache write tokens (creating cache)
        db_pricing: Optional pricing from database (overrides hardcoded table)

    Returns:
        Cost in USD
    """
    pricing = db_pricing or get_fallback_pricing(model_id)

    input_price = pricing.get("input", pricing.get("prompt", 3.0))
    output_price = pricing.get("output", pricing.get("completion", 12.0))
    cached_price = pricing.get("cached_input", pricing.get("cached", input_price * 0.25))

    non_cached_prompt = max(0, prompt_tokens - cached_tokens - cache_creation_tokens)

    cost = (
        (non_cached_prompt * input_price / 1_000_000)
        + (cached_tokens * cached_price / 1_000_000)
        + (cache_creation_tokens * input_price / 1_000_000)
        + (completion_tokens * output_price / 1_000_000)
    )

    return round(cost, 6)
