"""Languages offered in the UI.

Codes are BCP 47 so the browser can show localized names via Intl.DisplayNames.
The English name is what goes into the prompt. Japanese, English and Chinese come first.
"""

LANGUAGES: list[tuple[str, str]] = [
    ("ja", "Japanese"),
    ("en", "English"),
    ("zh-Hans", "Simplified Chinese"),
    ("zh-Hant", "Traditional Chinese"),
    ("ko", "Korean"),
    ("fr", "French"),
    ("de", "German"),
    ("es", "Spanish"),
    ("pt", "Portuguese"),
    ("it", "Italian"),
    ("ru", "Russian"),
    ("uk", "Ukrainian"),
    ("pl", "Polish"),
    ("nl", "Dutch"),
    ("sv", "Swedish"),
    ("da", "Danish"),
    ("nb", "Norwegian (Bokmål)"),
    ("fi", "Finnish"),
    ("cs", "Czech"),
    ("hu", "Hungarian"),
    ("ro", "Romanian"),
    ("bg", "Bulgarian"),
    ("el", "Greek"),
    ("tr", "Turkish"),
    ("ar", "Arabic"),
    ("he", "Hebrew"),
    ("fa", "Persian"),
    ("hi", "Hindi"),
    ("bn", "Bengali"),
    ("ur", "Urdu"),
    ("ta", "Tamil"),
    ("th", "Thai"),
    ("vi", "Vietnamese"),
    ("id", "Indonesian"),
    ("ms", "Malay"),
    ("fil", "Filipino"),
    ("sw", "Swahili"),
    ("mn", "Mongolian"),
]

AUTO = "auto"

LANGUAGE_NAMES: dict[str, str] = dict(LANGUAGES)
