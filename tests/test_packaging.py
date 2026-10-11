"""Check local HACS metadata and HA's service/translation input schemas."""

import json
from pathlib import Path

import yaml
from homeassistant.helpers.service import _SERVICES_SCHEMA
from PIL import Image

PATH = Path(__file__).parents[1] / "custom_components" / "digikabu"


def leaf_keys(value, prefix=""):
    keys = set()
    for key, child in value.items():
        path = f"{prefix}.{key}"
        if isinstance(child, dict):
            keys |= leaf_keys(child, path)
        else:
            keys.add(path)
    return keys


def test_metadata_and_translations():
    root = PATH.parents[1]
    manifest = json.loads((PATH / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((root / "hacs.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "digikabu"
    assert manifest["config_flow"] is True
    assert manifest["requirements"] == []
    assert hacs["homeassistant"] == "2026.10.1"
    strings = json.loads((PATH / "strings.json").read_text(encoding="utf-8"))
    for language in ("en", "de"):
        translated = json.loads(
            (PATH / "translations" / f"{language}.json").read_text(encoding="utf-8")
        )
        assert leaf_keys(translated) == leaf_keys(strings)
        if language == "en":
            assert translated == strings
    descriptions = _SERVICES_SCHEMA(
        yaml.safe_load((PATH / "services.yaml").read_text(encoding="utf-8"))
    )
    assert descriptions.keys() == strings["services"].keys()
    for service, description in descriptions.items():
        assert description["fields"].keys() == (
            strings["services"][service]["fields"].keys()
        )


def test_student_only_request_paths():
    source = (PATH / "api.py").read_text(encoding="utf-8")
    for excluded in (
        "/api/klassen",
        "/api/lehrer",
        "/api/schueler/foto",
        "/api/schueler/allstudentsandteachers",
        "/api/stundenplan/klasse",
        "/api/stundenplan/lehrer",
        "/api/termine/schulaufgaben/",
    ):
        assert excluded not in source


def test_hacs_brand_asset():
    with Image.open(PATH / "brand" / "icon.png") as image:
        assert image.format == "PNG"
        assert image.size == (256, 256)
