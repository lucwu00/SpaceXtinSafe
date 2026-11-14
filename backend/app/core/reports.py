"""Mission evidence report (PDF) built from the same services the UI uses."""
from __future__ import annotations
import io, datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from . import analysis, audit, models, store, data

VERSION = "1.1.0"
DISCLAIMER = ("SpaceXtinSafe is an independent research and educational prototype. This report is not a certified spacecraft fire safety assessment, "
              "material qualification, operational recommendation, emergency procedure or NASA-endorsed product.")


def _t(rows, widths):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 7.5), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8c4d0")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def build(spacecraft_id: str, scenario: dict | None = None, prediction: dict | None = None, interaction_ids: list | None = None,
          compare_ids: list | None = None, incident: dict | None = None) -> bytes:
    sc = store.get_spacecraft(spacecraft_id)
    ss = getSampleStyleSheet(); P = lambda s, st="BodyText": Paragraph(s, ss[st])
    small = ParagraphStyle("s", parent=ss["BodyText"], fontSize=7.5, leading=9)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"SpaceXtinSafe mission evidence report - {sc['name']}")
    s = [P("SpaceXtinSafe — Mission Evidence Report", "Title"), P(f"{sc['name']} · {sc['vehicle_class']} · generated {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC"),
         Spacer(1, 4), P(DISCLAIMER, "Italic"), Spacer(1, 6), P("1. Configuration", "Heading2")]
    a = sc["atmosphere"]
    s.append(P(f"Atmosphere: {a['o2_pct']}% O2 (O2 partial pressure {a['o2_pct'] / 100 * a['pressure_kpa']:.1f} kPa), {a['pressure_kpa']} kPa, {a['gravity']}, ventilation {a.get('ventilation_cm_s')} cm/s, diluent {a.get('diluent')}. Origin: {sc.get('origin', '-')}."))
    s.append(P("<b>Mission manifest</b>"))
    s.append(_t([["Compartment", "Object", "Components (material)"]] + [[c["name"], o["name"], Paragraph("; ".join(f"{k['name']} ({data.materials().get(k['material_id'], {}).get('name', k['material_id'])}{', user-defined' if data.materials().get(k['material_id'], {}).get('user_defined') else ''})" for k in o["components"]), small)]
                 for c in sc["compartments"] for o in c["objects"]], [35 * mm, 38 * mm, 105 * mm]))
    scr = analysis.screen(spacecraft_id)
    s += [P("2. Material evidence screening", "Heading2"),
          _t([["Compartment", "Object / component", "Material", "Evidence status", "Investigations"]] +
             [[r["compartment"], Paragraph(f"{r['object']} / {r['component']}", small), Paragraph(r["material"], small), Paragraph(r["status"], small),
               Paragraph(", ".join(r["investigations"]) or "-", small)] for r in scr["rows"]], [28 * mm, 45 * mm, 32 * mm, 38 * mm, 35 * mm]),
          Spacer(1, 3), P(scr["boundary"], "Italic")]
    if scenario:
        ins = analysis.insights(scenario)
        s += [P("3. Scenario insights", "Heading2"), P(f"Scenario: {scenario}")]
        for k, lab in (("observed", "What NASA observed"), ("historical", "Historical analogues"), ("uncertain", "What remains uncertain"), ("next", "Next investigations")):
            if ins[k]:
                s.append(P(f"<b>{lab}</b>"))
                for x in ins[k]:
                    s.append(P(f"• {x['text']}" + (f" [{x['cite']}]" if x.get("cite") else ""), "BodyText"))
    if prediction:
        s += [P("4. Prediction eligibility", "Heading2"), P(f"Outcome: <b>{prediction['outcome']}</b>" + (f" — {prediction['estimate']:.3f} mm²/s" if prediction.get("estimate") is not None else ""))]
        s.append(_t([["Check", "Result", "Detail"]] + [[c["check"], "pass" if c["result"] else "fail", Paragraph(c["detail"], small)] for c in prediction["checks"]], [55 * mm, 15 * mm, 108 * mm]))
        s.append(P("Reasons: " + "; ".join(prediction["reasons"])))
    if interaction_ids and len(interaction_ids) >= 2:
        it = analysis.interaction(interaction_ids)
        s += [P("Material interaction evidence", "Heading2"), P(f"{', '.join(it['materials'])}: <b>{it['status']}</b>. {it['note']}")]
        for e in it["documented_interactions"] + it["co_reported"]:
            s.append(P(f"• {e['statement']} [{e['id']}]"))
    if compare_ids and len(compare_ids) >= 2:
        cp = analysis.compare(compare_ids)
        s += [P("Configuration comparison", "Heading2"), _t([["Configuration", "Atmosphere", "Components", "Gap materials"]] + [[c["name"], f"{c['atmosphere']['o2_pct']}% / {c['atmosphere']['pressure_kpa']} kPa / {c['atmosphere']['gravity']}", c["components"], Paragraph(", ".join(c["gap_materials"]) or "-", small)] for c in cp["configurations"]], [40 * mm, 50 * mm, 22 * mm, 66 * mm])]
    if incident and incident.get("compartment_id"):
        from . import incidents as inc
        r = inc.replay(spacecraft_id, incident["compartment_id"], incident.get("type", "smoke"), incident.get("phase", "orbital operations"))
        s += [P("Simulated incident (training scenario)", "Heading2"), P(r.get("human_review_summary") or r.get("message", "")),
              P("No emergency instructions are generated. Real events follow the vehicle's authorised procedures.", "Italic")]
    gp = analysis.gaps(spacecraft_id)
    zero = sorted({c["material"] for c in gp["cells"] if c["count"] == 0 and c["condition"] == "Microgravity"})
    s += [P("Research gaps (this library)", "Heading2"), P("Materials on board with no microgravity finding in the library: " + (", ".join(zero) or "none") + ". " + gp["note"])]
    au = audit.run()
    s += [PageBreak(), P("5. Evidence audit summary", "Heading2"), P(", ".join(f"{k}: {v}" for k, v in au["classification_counts"].items())),
          _t([["ID", "Classification", "Quantity", "Values (source A / B)"]] + [[Paragraph(i["id"], small), Paragraph(i["classification"], small), Paragraph(i["quantity"], small),
             Paragraph(" / ".join(str(v.get("raw")) for v in i["values"]), small)] for i in au["items"] if i["status"] != "Missing information" or i["investigation"] != "FLEX"],
             [48 * mm, 32 * mm, 40 * mm, 58 * mm]),
          P("6. Models", "Heading2"),
          _t([["Model", "Status", "n / sessions", "Params", "OOF MAE", "Skill"]] + [[m["model_id"], m["status"], f"{m['n_observations']} / {m['n_sessions']}", m["n_parameters"],
             f"{m['validation']['mae']:.3f}", f"{m['validation']['predictive_skill']:.2f}"] for m in models.registry()], [42 * mm, 30 * mm, 24 * mm, 14 * mm, 22 * mm, 18 * mm]),
          P("7. Methodology", "Heading2"),
          P("Evidence: 42 statements with verbatim quotes machine-checked against NASA source PDFs. Applicability: per-factor comparison (material, form, gravity, O2, pressure, flow); "
            "unreported factors are never counted as matches. Models: OLS with intercept, leave-one-session-out validation, RF and mean-baseline benchmarks; estimates only after "
            "condition, pressure-band, convex-hull, nearest-neighbour and local-coverage checks. Audit: automated cross-source comparison with stated tolerances."),
          P("8. AI usage disclosure", "Heading2"),
          P("Retrieval uses BM25, sentence-transformer embeddings (all-MiniLM-L6-v2) and knowledge-graph traversal. The optional Claude copilot writes answers only from retrieved "
            "evidence; claims failing citation and number checks are removed. No AI-generated content appears in this report except where labelled. The app, data curation and "
            "evaluation labels were produced with AI assistance and reviewed by the team."),
          P(f"Versions: app {VERSION}; models {', '.join(m['model_id'] + ' (' + m['status'] + ')' for m in models.registry())}; evidence statements {len(data.evidence())}."),
          P("9. Sources", "Heading2")]
    for x in data.sources().values():
        s.append(Paragraph(f"{x['id']}: {x['title']} ({x['identifier']}) {x['url']}", small))
    doc.build(s)
    return buf.getvalue()
