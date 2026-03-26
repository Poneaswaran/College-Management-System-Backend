import uuid


def generate_card_number(prefix, identity_code):
    safe_identity = (identity_code or "UNKNOWN").replace(" ", "").upper()
    suffix = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{safe_identity}-{suffix}"


def generate_card_number_from_format(prefix, identity_code, format_pattern="PREFIX-ID-RANDOM"):
    safe_identity = (identity_code or "UNKNOWN").replace(" ", "").upper()
    random_value = uuid.uuid4().hex[:8].upper()

    pattern = str(format_pattern or "PREFIX-ID-RANDOM")
    return (
        pattern.replace("PREFIX", prefix)
        .replace("ID", safe_identity)
        .replace("RANDOM", random_value)
    )
