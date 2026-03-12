LANGUAGE_MAP = {

    "ja": "Japanese",
    "en": "English",
    "th": "Thai",
    "ko": "Korean",
    "zh": "Chinese",
    "fr": "French",
    "es": "Spanish",
    "ru": "Russian",
    "pt": "Portuguese",
    "it": "Italian",
    "de": "German",
    "vi": "Vietnamese",
    "id": "Indonesian"
}


def language_name(code: str):

    return LANGUAGE_MAP.get(code, code)