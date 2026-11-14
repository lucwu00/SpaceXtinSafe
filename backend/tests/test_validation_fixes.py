"""Regression tests for defects found by scripts/validate_science.py (2026-11-15)."""
from app.core import data, models, store, copilot


def test_user_alias_cannot_take_over_catalogue_material():
    rec = store.save_material({"name": "pytest alias collision", "form": "sheet", "aliases": ["PMMA"]})
    try:
        assert data.material_status("MAT-PMMA")["status"] == data.STATUS_ORDER[0]
        assert data.material_status(rec["id"])["status"] == data.STATUS_ORDER[4]
    finally:
        store.delete_material(rec["id"])


def test_non_numeric_prediction_input_is_unavailable_not_an_error():
    a = models.assess(dict(material_form="liquid droplet", fuel="methanol", o2_pct="abc", pressure_kpa=101.3, d0_mm=2.5, diluent="nitrogen", gravity="microgravity"))
    assert a["outcome"] == "Unavailable" and a["estimate"] is None


def test_spacecraft_element_question_is_not_abstained_for_low_cosine():
    r = copilot.ask("What NASA evidence exists for the materials in the sleeping bag?", None, "SC-ORBITAL")
    assert r["mode"] != "no-evidence"
