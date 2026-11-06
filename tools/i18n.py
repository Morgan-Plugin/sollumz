import json
from pathlib import Path

LOCALES_DIR = Path(__file__).parent.parent / "locales"

# Module name used when registering translations with Blender.
# Must be a unique string, and the same one for register and unregister.
I18N_MODULE_NAME = "sollumz"

SUPPORTED_LOCALES = ("en_US", "zh_CN")

# Blender locale keys each supported locale should be registered under.
# Blender 4.x+ uses "zh_HANS" for simplified Chinese.
BLENDER_LOCALE_KEYS = {
    "en_US": ("en_US",),
    "zh_CN": ("zh_CN", "zh_HANS"),
}

# locale key -> {msgid: msgstr}
_translations: dict[str, dict[str, str]] = {}


def _normalize_locale(locale: str) -> str:
    """Map a Blender locale key to a supported locale name."""
    if locale in SUPPORTED_LOCALES:
        return locale
    for name, keys in BLENDER_LOCALE_KEYS.items():
        if locale in keys:
            return name
    return "en_US"


def load_translations() -> None:
    """Load all locale JSON files from the locales directory."""
    _translations.clear()

    for locale in SUPPORTED_LOCALES:
        path = LOCALES_DIR / f"{locale}.json"
        if not path.is_file():
            continue

        with path.open(encoding="utf-8") as f:
            table = json.load(f)

        if isinstance(table, dict):
            _translations[locale] = table


def get_preferred_locale() -> str:
    """Get the locale set in the Sollumz preferences, or Blender's locale when set to AUTO."""
    import bpy

    prefs = bpy.context.preferences.addons.get("sollumz")
    if prefs is not None and hasattr(prefs.preferences, "sollumz_language"):
        language = prefs.preferences.sollumz_language
        if language != "AUTO":
            return language

    locale = bpy.app.translations.locale
    return _normalize_locale(locale)


def t(msgid: str) -> str:
    """Translate msgid into the preferred locale. Returns msgid unchanged when there is no translation."""
    if not _translations:
        load_translations()

    table = _translations.get(get_preferred_locale())
    if not table:
        return msgid

    return table.get(msgid, msgid)


def _build_translations_dict(locale: str, table: dict[str, str]) -> dict:
    # UI lookups do not fall back to the "*" wildcard context, so register
    # each msgid under every context Blender uses:
    #   "*"        -> default-context lookups (layout text, some tooltips)
    #   "Operator" -> operator button names and their tooltips
    #   "bpy.types"-> descriptions of Python-registered types/properties
    #                 (property tooltips, panel/operator descriptions)
    translations = {}
    for msgid, msgstr in table.items():
        translations[("*", msgid)] = msgstr
        translations[("Operator", msgid)] = msgstr
        translations[("bpy.types", msgid)] = msgstr
    return translations


def _register_translations_dict() -> None:
    import bpy

    # Unregister first so the registration is idempotent. Blender may call
    # register() more than once when loading extensions, and registering the
    # same module name twice raises a ValueError that interrupts registration.
    translations_dict = {}
    for locale, table in _translations.items():
        for blender_key in BLENDER_LOCALE_KEYS[locale]:
            translations_dict[blender_key] = _build_translations_dict(blender_key, table)

    bpy.app.translations.unregister(I18N_MODULE_NAME)
    bpy.app.translations.register(I18N_MODULE_NAME, translations_dict)


def register() -> None:
    load_translations()
    _register_translations_dict()


def unregister() -> None:
    import bpy

    bpy.app.translations.unregister(I18N_MODULE_NAME)
    _translations.clear()


def language_update(_self, context) -> None:
    """Callback for the language preference. Re-registers the translation tables
    so the UI updates immediately, then redraws the UI."""
    import bpy

    bpy.app.translations.unregister(I18N_MODULE_NAME)

    load_translations()

    language = _self.sollumz_language
    if language == "AUTO":
        # Follow Blender: register every locale table under its own locale key.
        _register_translations_dict()
    elif language == "en_US":
        # Force English: register nothing, all labels fall back to their English source text.
        pass
    else:
        # Force a locale: register its table under every Blender locale key so
        # the UI shows this language regardless of the Blender interface language.
        table = _translations.get(language, {})
        translations_dict = {}
        for locale in SUPPORTED_LOCALES:
            for blender_key in BLENDER_LOCALE_KEYS[locale]:
                translations_dict[blender_key] = _build_translations_dict(blender_key, table)

        bpy.app.translations.register(I18N_MODULE_NAME, translations_dict)

    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()
