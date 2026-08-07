def generate_genitive(latin_nominative: str) -> str:
    value = (latin_nominative or "").strip()
    if not value:
        return ""

    if value.endswith("um"):
        return f"{value[:-2]}i"
    if value.endswith("a"):
        return f"{value[:-1]}ae"
    if value.endswith("is"):
        return value
    if value.endswith("us"):
        return f"{value[:-2]}i"
    return value
