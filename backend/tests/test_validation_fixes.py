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


def test_paper_in_publication_sense_is_not_the_material():
    from app.core import retrieval
    assert "MAT-PAPER" not in retrieval.entities("What were the objectives according to the 2016 Saffire objectives paper?")
    assert "MAT-PAPER" in retrieval.entities("What NASA evidence exists for paper?")


def test_library_question_is_not_routed_to_app_help():
    from app.core import router
    assert router.kind_of("What does the library say about silicone?") != "app"
    assert router.kind_of("What can you do?") == "app"


def test_value_and_attribute_rules():
    assert copilot.VALUE_Q.search("At what oxygen pressure did sparks ignite combustibles?")
    ev = [{"id": "E1", "statement": "LUCI burned fabric at lunar gravity.", "quote": "flame spread"}]
    assert copilot._attr_missing("What sample sizes were flown?", [{"text": "x", "citations": ["E1"]}], ev) == ["size"]


def test_dimension_stated_as_length_counts_but_rate_does_not():
    sheet = [{"id": "E1", "statement": "a 40.6 cm wide, 0.37 mm sheet", "quote": ""}]
    rate = [{"id": "E2", "statement": "spread rate 0.92 mm/s", "quote": ""}]
    q = "What were the width and thickness of the sample?"
    assert copilot._attr_missing(q, [{"text": "x", "citations": ["E1"]}], sheet) == []
    assert copilot._attr_missing("What sample sizes were flown?", [{"text": "x", "citations": ["E2"]}], rate) == ["size"]
