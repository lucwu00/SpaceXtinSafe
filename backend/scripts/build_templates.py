"""Generates the three illustrative spacecraft templates (generic, not real vehicles)."""
import json, os
OUT = os.path.join(os.path.dirname(__file__), "..", "app", "data", "curated", "spacecraft_templates.json")
K = lambda i, n, m, f, t=None, g=None: {"id": i, "name": n, "material_id": m, "form": f, "thickness_mm": t, "mass_g": g}
O = lambda i, n, cat, comps: {"id": i, "name": n, "category": cat, "components": comps}
S = lambda *types: [{"id": f"S{i+1}", "type": t} for i, t in enumerate(types)]
LAPTOP = lambda p: O(f"O-LAPTOP{p}", "Crew laptop", "electronics", [K(f"K-LAP-BATT{p}", "Battery pack", "MAT-LIION", "cell", None, 300), K(f"K-LAP-CASE{p}", "Polymer enclosure", "MAT-POLYC", "moulded part", 2.0, 500),
    K(f"K-LAP-PCB{p}", "Printed circuit board", "MAT-PCB", "board", 1.6, 150), K(f"K-LAP-CU{p}", "Copper wiring", "MAT-COPPER", "wire", 0.3, 40), K(f"K-LAP-INS{p}", "Cable insulation", "MAT-CABLEINS", "wire insulation", 0.3, 20),
    K(f"K-LAP-DISP{p}", "Display assembly", "MAT-DISPLAY", "assembly", None, 400), K(f"K-LAP-ADH{p}", "Adhesives", "MAT-ADHESIVE", "adhesive layer", 0.1, 5)])
T = [
 {"id": "TPL-ORBITAL", "name": "Orbital Research Module", "vehicle_class": "Orbital laboratory (generic, illustrative)", "shape": "module",
  "description": "A generic microgravity laboratory module with a sea-level air atmosphere. Illustrative layout, not a real or certified vehicle.",
  "atmosphere": {"o2_pct": 21.0, "pressure_kpa": 101.3, "gravity": "microgravity", "ventilation_cm_s": 15, "diluent": "nitrogen"},
  "compartments": [
   {"id": "C-LAB", "name": "Laboratory bay", "type": "laboratory", "volume_m3": 35, "x": 0, "y": 0, "w": 34, "h": 40, "sensors": S("smoke", "O2", "CO"), "objects": [
     O("O-RACK", "Experiment rack", "equipment", [K("K-RACK-FRAME", "Rack frame", "MAT-ALU", "bulk", 3.0, 20000), K("K-RACK-WIN", "Acrylic sample window", "MAT-PMMA", "thin sheet", 2.0, 300)]),
     O("O-FUEL", "Combustion research fuel vial", "experiment", [K("K-FUEL-M", "Methanol fuel reservoir", "MAT-METHANOL", "liquid droplet", None, 5)]),
     O("O-HARNESS", "Cable harness", "power", [K("K-HARN-W", "Copper conductors", "MAT-WIRING", "wire", 1.0, 800), K("K-HARN-INS", "Wire insulation", "MAT-PTFE", "wire insulation", 0.25, 120)]),
     O("O-WALL", "Wall panel", "structure", [K("K-WALL-AL", "Structural alloy skin", "MAT-ALU", "bulk", 2.0, 9000), K("K-WALL-CFRP", "Composite layer", "MAT-CFRP", "laminate", 1.5, 2500),
       K("K-WALL-MLI", "Thermal insulation", "MAT-MLI", "blanket", 5.0, 400), K("K-WALL-ADH", "Adhesive layer", "MAT-ADHESIVE", "adhesive layer", 0.2, 80), K("K-WALL-COAT", "Surface coating", "MAT-COATING", "coating", 0.05, 30)])]},
   {"id": "C-AVIONICS", "name": "Avionics bay", "type": "avionics", "volume_m3": 6, "x": 34, "y": 0, "w": 20, "h": 18, "sensors": S("smoke", "temperature"), "objects": [
     O("O-COMPUTER", "Flight computer", "electronics", [K("K-FC-PCB", "Circuit boards", "MAT-PCB", "board", 1.6, 600), K("K-FC-CONN", "Connectors", "MAT-CONNECTOR", "assembly", None, 120),
       K("K-FC-ENC", "Enclosure", "MAT-ENCLOSURE", "moulded part", 2.0, 1500), K("K-FC-KAP", "Flex circuits", "MAT-KAPTON", "film", 0.05, 10)]),
     O("O-PDU", "Power distribution unit", "power", [K("K-PDU-CU", "Bus bars", "MAT-COPPER", "bulk", 3.0, 900), K("K-PDU-INS", "Cable insulation", "MAT-CABLEINS", "wire insulation", 0.3, 200)])]},
   {"id": "C-CREW", "name": "Crew quarters", "type": "habitation", "volume_m3": 12, "x": 34, "y": 18, "w": 20, "h": 22, "sensors": S("smoke", "CO"), "objects": [
     O("O-CLOTH", "Crew clothing stowage", "crew provisions", [K("K-CLOTH", "Cotton garments", "MAT-COTTON", "fabric", 0.4, 2000), K("K-CLOTH-STRAP", "Hook-and-loop straps", "MAT-NYLON", "fabric", 1.0, 60)]),
     O("O-BAG", "Sleeping bag", "crew provisions", [K("K-BAG-SHELL", "Shell fabric", "MAT-NOMEX", "fabric", 0.4, 900), K("K-BAG-INNER", "Inner fabric", "MAT-POLYESTER", "fabric", 0.3, 400),
       K("K-BAG-FILL", "Padding", "MAT-PU", "foam", 20, 700), K("K-BAG-FAST", "Fasteners", "MAT-NYLON", "hook-and-loop", 1.0, 40), K("K-BAG-ZIP", "Zipper", "MAT-PE", "moulded part", 2.0, 30)]),
     LAPTOP(""),
     O("O-PERSONAL", "Personal items kit", "crew provisions", [K("K-PERS-BOOK", "Notebook", "MAT-PAPER", "stack", 10, 250), K("K-PERS-TOIL", "Toiletries", "MAT-TOILETRY", "container", None, 300),
       K("K-PERS-WIPE", "Cleaning wipes", "MAT-ALCOHOLWIPE", "fabric", 0.3, 120)])]},
   {"id": "C-GALLEY", "name": "Galley", "type": "food preparation", "volume_m3": 8, "x": 54, "y": 0, "w": 22, "h": 40, "sensors": S("smoke"), "objects": [
     O("O-FOOD", "Food stowage", "food", [K("K-FOOD-POUCH", "Food packaging film", "MAT-FOODFILM", "film", 0.1, 400), K("K-FOOD-DRY", "Dried food", "MAT-DRYFOOD", "solid", None, 3000),
       K("K-FOOD-BOX", "Cardboard cartons", "MAT-CARDBOARD", "sheet", 2.0, 500)]),
     O("O-WASTE", "Waste container", "waste", [K("K-WASTE-BAG", "Waste bags", "MAT-WASTEBAG", "film", 0.05, 100), K("K-WASTE-ORG", "Organic waste", "MAT-WASTE", "mixed", None, 1500)])]},
   {"id": "C-ECLSS", "name": "Life support bay", "type": "environmental control", "volume_m3": 10, "x": 76, "y": 0, "w": 24, "h": 40, "sensors": S("smoke", "O2", "CO", "CO2"), "objects": [
     O("O-O2GEN", "Backup oxygen generator", "life support", [K("K-SFOG", "Solid-fuel oxygen canister", "MAT-SFOG", "canister", None, 1500)]),
     O("O-O2LINE", "Oxygen distribution line", "life support", [K("K-O2-VALVE", "Regulator and valve", "MAT-O2VALVE", "assembly", None, 600), K("K-O2-TUBE", "Tubing", "MAT-NI", "bulk", 1.0, 400)]),
     O("O-SEAL", "Hatch seal", "structure", [K("K-SEAL", "Seal", "MAT-SILICONE", "thin sheet", 1.0, 200)])]}]},
 {"id": "TPL-CAPSULE", "name": "Crew Capsule", "vehicle_class": "Crew transport capsule (generic, illustrative)", "shape": "capsule",
  "description": "A compact generic crew capsule with a sea-level air cabin. Illustrative layout, not a real or certified vehicle.",
  "atmosphere": {"o2_pct": 21.0, "pressure_kpa": 101.3, "gravity": "microgravity", "ventilation_cm_s": 10, "diluent": "nitrogen"},
  "compartments": [
   {"id": "C-CABIN", "name": "Crew cabin", "type": "habitation", "volume_m3": 9, "x": 0, "y": 0, "w": 58, "h": 40, "sensors": S("smoke", "O2", "CO"), "objects": [
     O("O-SEATS", "Crew seats", "structure", [K("K-SEAT-PAD", "Seat padding", "MAT-PU", "foam", 25, 1500), K("K-SEAT-COVER", "Seat cover", "MAT-NOMEX", "fabric", 0.4, 400), K("K-SEAT-FRAME", "Seat frame", "MAT-TI64", "bulk", 3.0, 6000)]),
     O("O-DISPLAY", "Display panel", "electronics", [K("K-DISP-HARN", "Panel wiring insulation", "MAT-PTFE", "wire insulation", 0.25, 80), K("K-DISP-WIN", "Acrylic bezel", "MAT-PMMA", "thin sheet", 1.5, 150),
       K("K-DISP-GLASS", "Display glass", "MAT-GLASS", "sheet", 1.0, 300)]),
     LAPTOP("-CAP")]},
   {"id": "C-AVIONICS", "name": "Avionics bay", "type": "avionics", "volume_m3": 2, "x": 58, "y": 0, "w": 42, "h": 16, "sensors": S("smoke", "temperature"), "objects": [
     O("O-COMPUTER", "Flight computer", "electronics", [K("K-FC-PCB", "Circuit boards", "MAT-PCB", "board", 1.6, 600), K("K-FC-ENC", "Enclosure", "MAT-ENCLOSURE", "moulded part", 2.0, 1500)])]},
   {"id": "C-STOW", "name": "Stowage bay", "type": "stowage", "volume_m3": 3, "x": 58, "y": 16, "w": 42, "h": 24, "sensors": S("smoke"), "objects": [
     O("O-CARGO", "Soft cargo bags", "stowage", [K("K-CARGO", "Bag fabric", "MAT-NOMEX", "fabric", 0.5, 600), K("K-CARGO-TOWEL", "Towels", "MAT-COTTON", "fabric", 2.0, 400)]),
     O("O-MEDKIT", "Medical kit", "crew provisions", [K("K-MED-SUP", "Medical supplies", "MAT-MEDKIT", "mixed", None, 800), K("K-MED-GLOVE", "Gloves", "MAT-NITRILE", "glove film", 0.1, 50), K("K-MED-MASK", "Masks", "MAT-MASK", "fabric", 0.3, 30)])]}]},
 {"id": "TPL-LUNAR", "name": "Lunar Surface Habitat", "vehicle_class": "Surface habitat (generic, illustrative)", "shape": "habitat",
  "description": "A generic lunar surface habitat using the 34% O2 / 56.5 kPa (8.2 psia) exploration atmosphere discussed in NASA research. Illustrative, not a real design.",
  "atmosphere": {"o2_pct": 34.0, "pressure_kpa": 56.5, "gravity": "partial gravity", "ventilation_cm_s": 10, "diluent": "nitrogen"},
  "compartments": [
   {"id": "C-HAB", "name": "Living area", "type": "habitation", "volume_m3": 40, "x": 0, "y": 0, "w": 40, "h": 40, "sensors": S("smoke", "O2", "CO"), "objects": [
     O("O-CURTAIN", "Privacy curtain", "crew provisions", [K("K-CURT", "Curtain fabric", "MAT-SIBAL", "thin fabric sheet", 0.37, 500)]),
     O("O-TABLE", "Galley table", "furniture", [K("K-TABLE-TOP", "Acrylic tabletop", "MAT-PMMA", "slab", 10, 3000), K("K-TABLE-LEG", "Legs", "MAT-MG", "bulk", 3.0, 1200)]),
     O("O-BUNK", "Sleep bunk", "crew provisions", [K("K-BUNK-MAT", "Mattress foam", "MAT-PU", "foam", 50, 2500), K("K-BUNK-COVER", "Mattress cover", "MAT-COTTON", "fabric", 0.5, 400)])]},
   {"id": "C-LAB", "name": "Science workstation", "type": "laboratory", "volume_m3": 15, "x": 40, "y": 0, "w": 30, "h": 20, "sensors": S("smoke", "CO"), "objects": [
     O("O-SAMPLE", "Sample processing kit", "experiment", [K("K-SAMPLE-ETOH", "Ethanol", "MAT-ETHANOL", "liquid", None, 200), K("K-SAMPLE-GLOVE", "Gloves", "MAT-NITRILE", "glove film", 0.1, 60)]),
     LAPTOP("-LUN")]},
   {"id": "C-ENG", "name": "Engineering bay", "type": "engineering", "volume_m3": 12, "x": 40, "y": 20, "w": 30, "h": 20, "sensors": S("smoke", "temperature"), "objects": [
     O("O-BATT", "Habitat battery module", "power", [K("K-BATT-CELL", "Battery cells", "MAT-LIION", "cell", None, 40000), K("K-BATT-SEP", "Separators", "MAT-SEPARATOR", "film", 0.02, 300)]),
     O("O-PUMP", "Coolant pump", "thermal control", [K("K-PUMP-COOL", "Coolant", "MAT-COOLANT", "liquid", None, 5000), K("K-PUMP-LUBE", "Lubricant", "MAT-LUBE", "grease", None, 50)])]},
   {"id": "C-AIRLOCK", "name": "Suit port and airlock", "type": "airlock", "volume_m3": 8, "x": 70, "y": 0, "w": 30, "h": 40, "sensors": S("smoke", "O2"), "objects": [
     O("O-SUITSTOW", "Suit maintenance kit", "EVA", [K("K-SUIT-SEAL", "Spare seals", "MAT-SILICONE", "thin sheet", 0.6, 100), K("K-SUIT-WIPES", "Cleaning wipes", "MAT-COTTON", "fabric", 0.3, 200),
       K("K-SUIT-FAB", "Suit fabric patches", "MAT-SUITFAB", "fabric", 1.0, 150)])]}]},
]
json.dump(T, open(OUT, "w"), indent=1)
print("templates", [(t["name"], len(t["compartments"]), sum(len(o["components"]) for c in t["compartments"] for o in c["objects"])) for t in T])
