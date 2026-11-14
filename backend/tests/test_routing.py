"""Multi-model routing: deterministic tier-0 tools, tier choice, safeguards, and that missing evidence abstains instead of escalating."""
import os
from fastapi.testclient import TestClient
from app.main import app
from app.core import router, copilot

c = TestClient(app)


def ask(q, mode="auto", sc="SC-ORBITAL"):
    return c.post("/api/copilot", json={"question": q, "spacecraft_id": sc, "mode": mode}).json()


def test_tier0_tools():
    r = ask("What is the oxygen partial pressure at 34% and 56.5 kPa?")
    assert r["routing"]["tier"] == 0 and r["result"]["po2_kpa"] == 19.21
    r = ask("Predict the burning rate of methanol at 21% oxygen with a 2.5 mm droplet")
    assert r["tool"] == "flex_model_prediction" and r["result"]["outcome"].startswith("Model-supported")
    r = ask("Predict the burning rate of methanol at 30% oxygen with a 1.7 mm droplet")
    assert r["result"]["outcome"] == "Unavailable" and "Reasons" in r["answer"]
    assert ask("How many FLEX tests are there?")["result"]["FLEX droplet tests (PSI-69)"] > 200
    assert ask("Where can I find the research gaps heatmap?")["navigate"] == "gaps"


def test_tier_selection_rules():
    s, f = router.complexity("What happened to Nomex in the Saffire experiments?", [], [])
    assert router.choose("", "auto", "science", s, f)[0] == 2
    q = "Do the Saffire flow measurements conflict across sources, and how do oxygen, pressure and gravity together change PMMA flame spread?"
    s, f = router.complexity(q, [], [])
    assert s >= 3 and router.choose(q, "auto", "science", s, f)[0] == 3
    assert router.choose("", "fast", "science", 5, f)[0] == 1
    assert router.choose("", "deep", "science", 0, f)[0] == 3
    assert router.kind_of("What can this app do?") == "app" and router.kind_of("What is a burning-rate constant?") == "term"


def test_missing_evidence_abstains_without_escalation(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-invalid-test-key")
    r = ask("What is the thermal conductivity of aerogel?", mode="deep")
    assert r["mode"] == "no-evidence" and r["routing"]["tier"] == 0 and not r["routing"].get("escalations")


def test_budget_safeguard_falls_back(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-invalid-test-key")
    monkeypatch.setattr(router, "BUDGET_USD", 0.0)
    r = ask("What did Saffire-II show about Nomex flame spread?")
    assert r["mode"] == "evidence-retrieval" and "spending safeguard" in r["routing"]["fallback"]


def test_usage_logged_and_models_configurable(monkeypatch):
    monkeypatch.setenv("SXS_MODEL_FAST", "claude-haiku-test")
    assert router.model_for(1) == "claude-haiku-test"
    u = c.get("/api/copilot/usage").json()
    assert u["requests"] > 0 and "limits" in u
    assert router.cost(2, 1_000_000, 0) == router.price(2)[0]


def test_blank_or_quoted_key_is_handled(monkeypatch):
    """Regression: a blank key (e.g. 'ANTHROPIC_API_KEY= ' in .env) reached the SDK as 'Authorization: Bearer  ',
    an illegal header that surfaced as APIConnectionError. Blank keys now mean 'not configured'; quotes/spaces are stripped."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", " ")
    assert router.api_key() is None and copilot._blocked("t").startswith("Claude is not active")
    monkeypatch.setenv("ANTHROPIC_API_KEY", '  "sk-test-key"  ')
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", " ")
    h = {k.lower(): v for k, v in dict(router.client().auth_headers).items()}
    assert "  " not in " ".join(h.values()) and any(v.endswith("sk-test-key") for v in h.values())