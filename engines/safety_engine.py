import bleach
from better_profanity import profanity

profanity.load_censor_words()

ALLOWED_TAGS = []
ALLOWED_ATTRIBUTES = {}

def clean_text(value, max_length=1000):
    value = (value or "").strip()
    value = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    value = profanity.censor(value)
    return value[:max_length]


def is_safe_text(value):
    value = value or ""
    return not profanity.contains_profanity(value)


def normalize_username(username):
    username = (username or "").strip().lower()
    return "".join(ch for ch in username if ch.isalnum() or ch in ["_", "."])[:32]
