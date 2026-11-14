"""Generates app/data/curated/materials.json: the SpaceXtinSafe material ontology.
Catalogue entries describe what a material is and where it could plausibly be used. They carry NO combustion properties;
evidence status is computed at runtime from the verified NASA findings. No entry claims flight use on a real vehicle."""
import json, os
OUT = os.path.join(os.path.dirname(__file__), "..", "app", "data", "curated", "materials.json")
C = "SpaceXtinSafe catalogue entry (descriptive only; no combustion properties assigned)"
# id, common name, scientific name, category, class, default form, other forms, applications, aliases, related_to, phenomenon, composition, grade
M = [
 # --- existing evidence-bearing materials (ids preserved) ---
 ("MAT-SIBAL","Cotton-fiberglass fabric (SIBAL)","Cotton/glass-fibre blended fabric","Interior textiles","fabric","thin fabric sheet",["fabric"],["NASA reference test fabric","curtains","stowage covers"],["cotton-fiberglass fabric","SIBAL","cotton-fiberglass"],["MAT-COTTON"],"material combustion",None,None),
 ("MAT-COTTON","Cotton","Cellulose fibre textile","Interior textiles","fabric","fabric",["thin fabric sheet","towel"],["clothing","towels","wipes"],["cotton","cotton jersey"],["MAT-SIBAL"],"material combustion","Cellulose",None),
 ("MAT-NOMEX","Nomex","Meta-aramid fibre fabric","Interior textiles","fabric","fabric",["felt"],["flight suits","bag shells","seat covers"],["Nomex"],["MAT-KEVLAR"],"material combustion","Poly(m-phenylene isophthalamide)",None),
 ("MAT-PMMA","PMMA (acrylic)","Poly(methyl methacrylate)","Polymers","polymer","thin sheet",["slab","rod","sphere","cylinder"],["windows","bezels","test samples"],["PMMA","acrylic"],[],"material combustion","(C5H8O2)n",None),
 ("MAT-SILICONE","Silicone","Polydimethylsiloxane elastomer","Elastomers and sealants","elastomer","thin sheet",["seal","sealant","foam"],["seals","gaskets","wire jackets"],["silicone","silicone rubber"],[],"material combustion","PDMS-based",None),
 ("MAT-METHANOL","Methanol","Methanol","Research fuels and chemicals","liquid fuel","liquid droplet",["liquid pool"],["combustion research fuel"],["methanol"],[],"material combustion","CH3OH",None),
 ("MAT-HEPTANE","n-Heptane","n-Heptane","Research fuels and chemicals","liquid fuel","liquid droplet",["liquid pool"],["combustion research fuel"],["n-heptane","heptane"],[],"material combustion","C7H16",None),
 ("MAT-NYLON","Nylon","Polyamide (PA6 / PA66)","Polymers","polymer","fabric",["strap","hook-and-loop","moulded part"],["straps","hook-and-loop fasteners","bags"],["nylon","Velcro"],[],"material combustion","Polyamide",None),
 ("MAT-PU","Polyurethane foam","Polyurethane","Foams and insulation","polymer foam","foam",["sheet"],["padding","packing foam","seat cushions"],["polyurethane"],[],"material combustion","Polyurethane",None),
 ("MAT-PTFE","PTFE (Teflon)","Polytetrafluoroethylene","Polymers","fluoropolymer","thin sheet",["wire insulation","tape"],["wire insulation","seals","tape"],["Teflon","PTFE"],[],"material combustion","(C2F4)n",None),
 ("MAT-WIRING","Electrical wiring assembly","Insulated conductor assembly","Electronics and electrical","assembly","wire",["harness"],["harnesses","power distribution"],["wiring"],["MAT-COPPER","MAT-PTFE"],"electrical ignition source (not a material combustion dataset)",None,None),
 ("MAT-LATEX","Latex","Natural rubber latex","Elastomers and sealants","elastomer","glove film",["film"],["gloves"],["latex"],["MAT-RUBBER"],"material combustion","cis-1,4-polyisoprene",None),
 ("MAT-SFOG","Solid-fuel oxygen generator","Chlorate candle oxygen generator","Oxygen systems","oxygen system","canister",[],["backup oxygen supply"],["solid-fuel oxygen generator"],[],"oxygen-source reaction (chemical oxygen generation)","Typically sodium chlorate + iron fuel (composition varies)",None),
 ("MAT-ALU","Aluminium alloy","Aluminium alloy","Metals and alloys","metal","bulk",["foil","powder","shavings","honeycomb"],["structure","racks","packaging foil"],["aluminum","aluminium"],[],"metal combustion (form-dependent; bulk vs powder differ)","Al + alloying elements",None),
 ("MAT-LIION","Lithium-ion battery cell","Lithium-ion electrochemical cell","Energy storage","energy storage","cell",["pack"],["laptops","tools","power banks"],["lithium-ion","li-ion battery"],[],"battery thermal runaway (not ordinary material combustion)",None,None),
 ("MAT-POLYC","Polycarbonate","Bisphenol-A polycarbonate","Polymers","polymer","thin sheet",["moulded part"],["enclosures","visors","containers"],["polycarbonate"],[],"material combustion","(C16H14O3)n",None),
 # --- structural and construction ---
 ("MAT-TI","Titanium alloy","Titanium alloy","Metals and alloys","metal","bulk",["powder","foil","shavings"],["fittings","pressure vessels","fasteners"],["titanium"],[],"metal combustion (form-dependent)","Ti + alloying elements",None),
 ("MAT-TI64","Titanium alloy Ti-6Al-4V","Ti-6Al-4V","Metals and alloys","metal","bulk",["powder"],["fittings","brackets"],["Ti-6Al-4V","Ti64"],["MAT-TI"],"metal combustion (form-dependent)","Ti, 6% Al, 4% V","Grade 5"),
 ("MAT-MG","Magnesium alloy","Magnesium alloy","Metals and alloys","metal","bulk",["powder","shavings"],["lightweight housings"],["magnesium"],[],"metal combustion (form-dependent)","Mg + alloying elements",None),
 ("MAT-SS","Stainless steel","Austenitic stainless steel","Metals and alloys","metal","bulk",["foil","mesh"],["tubing","fasteners","galley equipment"],["stainless steel","304","316"],[],"metal combustion (form-dependent)","Fe-Cr-Ni",None),
 ("MAT-STEEL","Aerospace steel","High-strength alloy steel","Metals and alloys","metal","bulk",[],["fasteners","mechanisms"],["alloy steel"],["MAT-SS"],"metal combustion (form-dependent)","Fe + alloying elements",None),
 ("MAT-COPPER","Copper","Copper and copper alloys","Metals and alloys","metal","wire",["bulk","foil"],["conductors","heat exchangers"],["copper","brass","bronze"],[],"metal combustion (form-dependent)","Cu",None),
 ("MAT-NI","Nickel-based alloy","Nickel superalloy (e.g. Inconel)","Metals and alloys","metal","bulk",["foil"],["oxygen-system tubing","high-temperature parts"],["Inconel","nickel alloy"],[],"metal combustion (form-dependent)","Ni-Cr-Fe",None),
 ("MAT-CFRP","Carbon-fibre-reinforced polymer","Carbon fibre / epoxy composite","Composites","composite","laminate",["panel"],["structure","panels"],["CFRP","carbon fibre","carbon fiber"],["MAT-EPOXY"],"material combustion","Carbon fibre in epoxy matrix",None),
 ("MAT-GFRP","Glass-fibre-reinforced polymer","Glass fibre / epoxy composite","Composites","composite","laminate",["panel"],["panels","enclosures"],["GFRP","fiberglass composite"],["MAT-EPOXY"],"material combustion","Glass fibre in polymer matrix",None),
 ("MAT-EPOXY","Epoxy resin","Epoxy thermoset","Composites","polymer","laminate",["adhesive","coating"],["composite matrix","potting","adhesives"],["epoxy"],[],"material combustion","Epoxide thermoset",None),
 ("MAT-HONEYCOMB","Honeycomb core","Aluminium or aramid honeycomb","Composites","composite","honeycomb",[],["sandwich panels"],["honeycomb"],["MAT-ALU","MAT-NOMEX"],"material combustion","Al or aramid paper core",None),
 ("MAT-ADHESIVE","Structural adhesive","Epoxy or acrylic structural adhesive","Elastomers and sealants","polymer","adhesive layer",[],["bonded joints"],["adhesive","structural adhesive"],["MAT-EPOXY"],"material combustion",None,None),
 ("MAT-CERAMIC","Technical ceramic","Alumina / silica ceramics","Ceramics and glass","ceramic","bulk",["tile","fibre"],["insulators","thermal parts"],["ceramic","alumina"],[],"generally non-combustible inorganic (not tested here)","Al2O3 / SiO2",None),
 ("MAT-GLASS","Glass","Silicate glass","Ceramics and glass","ceramic","sheet",["fibre"],["windows","displays"],["glass"],[],"generally non-combustible inorganic (not tested here)","SiO2-based",None),
 ("MAT-COATING","Protective coating","Paint / conformal coating","Coatings","polymer","coating",[],["surface protection","conformal coating"],["paint","coating","conformal coating"],[],"material combustion",None,None),
 # --- interior polymers and furnishings ---
 ("MAT-PE","Polyethylene","Polyethylene","Polymers","polymer","film",["bag","moulded part"],["bags","food packaging","containers"],["polyethylene","HDPE","LDPE"],[],"material combustion","(C2H4)n",None),
 ("MAT-PP","Polypropylene","Polypropylene","Polymers","polymer","moulded part",["film"],["containers","utensils"],["polypropylene"],[],"material combustion","(C3H6)n",None),
 ("MAT-PVC","PVC","Poly(vinyl chloride)","Polymers","polymer","thin sheet",["wire insulation","film"],["cable jackets","bags"],["PVC","vinyl"],[],"material combustion","(C2H3Cl)n",None),
 ("MAT-POLYESTER","Polyester","Poly(ethylene terephthalate) fibre","Interior textiles","fabric","fabric",["film"],["clothing","bags","liners"],["polyester","PET fabric"],["MAT-MYLAR"],"material combustion","PET",None),
 ("MAT-KEVLAR","Kevlar","Para-aramid fibre fabric","Interior textiles","fabric","fabric",[],["protective covers","straps"],["Kevlar","para-aramid"],["MAT-NOMEX"],"material combustion","Poly(p-phenylene terephthalamide)",None),
 ("MAT-RUBBER","Rubber","Synthetic or natural rubber","Elastomers and sealants","elastomer","bulk",["sheet","seal"],["grips","seals","bumpers"],["rubber","EPDM","neoprene"],["MAT-LATEX","MAT-SILICONE"],"material combustion",None,None),
 ("MAT-SEALANT","Sealant","RTV silicone / polysulfide sealant","Elastomers and sealants","elastomer","sealant",[],["joint sealing"],["sealant","RTV"],["MAT-SILICONE"],"material combustion",None,None),
 ("MAT-FLOOR","Flooring laminate","Polymer floor covering","Interior textiles","polymer","sheet",[],["floors","foot restraints"],["flooring"],[],"material combustion",None,None),
 ("MAT-PANEL","Interior panel","Polymer or composite interior panel","Composites","composite","panel",[],["close-out panels"],["interior panel","closeout panel"],["MAT-GFRP","MAT-POLYC"],"material combustion",None,None),
 ("MAT-ACOUSTIC","Acoustic insulation","Polymer or glass-fibre acoustic blanket","Foams and insulation","polymer foam","blanket",[],["noise reduction"],["acoustic insulation","acoustic blanket"],["MAT-PU","MAT-FIBERGLASS"],"material combustion",None,None),
 # --- electronics ---
 ("MAT-PCB","Printed circuit board (FR-4)","Glass-epoxy laminate with copper","Electronics and electrical","composite","board",[],["electronics"],["PCB","FR-4","circuit board"],["MAT-EPOXY","MAT-COPPER"],"material combustion and electrical ignition source",None,"FR-4"),
 ("MAT-CONNECTOR","Electrical connector","Metal contacts in polymer housing","Electronics and electrical","assembly","assembly",[],["connectors"],["connector"],["MAT-COPPER"],"electrical ignition source",None,None),
 ("MAT-CABLEINS","Cable insulation (generic)","Polymer cable jacket","Electronics and electrical","polymer","wire insulation",[],["cable jackets"],["cable insulation","wire insulation"],["MAT-PTFE","MAT-PVC","MAT-SILICONE"],"material combustion and electrical ignition source",None,None),
 ("MAT-ENCLOSURE","Electronic enclosure","Polymer or metal enclosure","Electronics and electrical","assembly","moulded part",[],["housings"],["enclosure","housing"],["MAT-POLYC","MAT-ALU"],"material combustion",None,None),
 ("MAT-SEPARATOR","Battery separator","Microporous polyolefin film","Energy storage","polymer","film",[],["Li-ion cells"],["separator"],["MAT-PE","MAT-PP"],"battery thermal runaway context",None,None),
 ("MAT-ELECTROLYTE","Battery electrolyte","Organic carbonate electrolyte with lithium salt","Energy storage","liquid","liquid",[],["Li-ion cells"],["electrolyte"],[],"battery thermal runaway context","e.g. LiPF6 in carbonates",None),
 ("MAT-DISPLAY","Display assembly","Glass, polymer films and electronics","Electronics and electrical","assembly","assembly",[],["screens"],["display","screen"],["MAT-GLASS","MAT-PCB"],"material combustion and electrical ignition source",None,None),
 # --- crew provisions ---
 ("MAT-PAPER","Paper","Cellulose paper","Crew provisions","cellulose","sheet",["stack","book"],["notebooks","procedures","books"],["paper","notebook","book"],["MAT-COTTON"],"material combustion","Cellulose",None),
 ("MAT-CARDBOARD","Cardboard","Corrugated cellulose board","Food, packaging and waste","cellulose","sheet",[],["packaging"],["cardboard"],["MAT-PAPER"],"material combustion","Cellulose",None),
 ("MAT-TOILETRY","Toiletries","Personal-care products (mixed formulations)","Crew provisions","consumable","container",[],["hygiene kits"],["toiletries","cosmetics","hygiene products"],[],"material combustion (formulation-dependent)",None,None),
 ("MAT-ALCOHOLWIPE","Cleaning wipes","Non-woven wipe with cleaning solution","Crew provisions","consumable","fabric",[],["cleaning"],["cleaning wipes","wipes"],["MAT-COTTON","MAT-POLYESTER"],"material combustion (solution-dependent)",None,None),
 ("MAT-NITRILE","Nitrile gloves","Nitrile butadiene rubber","Crew provisions","elastomer","glove film",[],["medical","lab"],["nitrile","gloves"],["MAT-LATEX","MAT-RUBBER"],"material combustion",None,None),
 ("MAT-MASK","Face masks","Polypropylene non-woven","Crew provisions","polymer","fabric",[],["medical supplies"],["mask"],["MAT-PP"],"material combustion",None,None),
 ("MAT-MEDKIT","Medical supplies","Mixed medical consumables","Crew provisions","consumable","mixed",[],["medical kit"],["medical supplies","bandages"],["MAT-COTTON"],"material combustion (mixed)",None,None),
 # --- food, packaging, waste ---
 ("MAT-FOODFILM","Food packaging film","Multilayer polymer/aluminium laminate","Food, packaging and waste","polymer","film",[],["food pouches"],["food packaging","pouch"],["MAT-PE","MAT-ALU"],"material combustion",None,None),
 ("MAT-OIL","Food oils and fats","Triglycerides","Food, packaging and waste","liquid fuel","liquid",[],["food"],["cooking oil","fat"],[],"material combustion",None,None),
 ("MAT-DRYFOOD","Dried food","Dehydrated foodstuffs","Food, packaging and waste","organic","solid",[],["food"],["dried food"],[],"material combustion",None,None),
 ("MAT-WASTE","Organic waste","Mixed organic waste","Food, packaging and waste","organic","mixed",[],["waste storage"],["waste","trash"],[],"material combustion (mixed)",None,None),
 ("MAT-WASTEBAG","Waste storage bag","Polyethylene bag","Food, packaging and waste","polymer","film",[],["waste"],["waste bag","trash bag"],["MAT-PE"],"material combustion",None,None),
 # --- specialised aerospace ---
 ("MAT-KAPTON","Kapton","Polyimide film","Aerospace specialty","polymer","film",["wire insulation","tape"],["wire insulation","flexible circuits"],["Kapton","polyimide"],[],"material combustion and electrical ignition (arc tracking context)","Polyimide",None),
 ("MAT-MYLAR","Mylar","BoPET film","Aerospace specialty","polymer","film",[],["insulation blankets","bags"],["Mylar","BoPET"],["MAT-POLYESTER"],"material combustion","Biaxially oriented PET",None),
 ("MAT-MLI","Multilayer insulation","Aluminised polymer film blanket","Aerospace specialty","polymer","blanket",[],["thermal blankets"],["MLI","multilayer insulation"],["MAT-KAPTON","MAT-MYLAR"],"material combustion","Aluminised Kapton/Mylar layers",None),
 ("MAT-TPS","Thermal protection material","Ablator or ceramic TPS","Aerospace specialty","ceramic","tile",[],["heat shields"],["heat shield","TPS","ablator"],[],"external aerodynamic heating (not internal cabin combustion)",None,None),
 ("MAT-AEROGEL","Aerogel","Silica aerogel","Foams and insulation","ceramic","blanket",[],["insulation"],["aerogel"],[],"generally inorganic (not tested here)","SiO2",None),
 ("MAT-FIBERGLASS","Fiberglass insulation","Glass-fibre batt","Foams and insulation","ceramic","blanket",[],["insulation"],["fiberglass","glass wool"],[],"generally non-combustible fibre; binders may burn (not tested here)",None,None),
 ("MAT-SUITFAB","Space suit fabric","Layered suit textiles (e.g. Ortho-fabric)","Aerospace specialty","fabric","fabric",[],["EVA suits"],["suit fabric","ortho-fabric"],["MAT-NOMEX","MAT-KEVLAR"],"material combustion",None,None),
 ("MAT-O2VALVE","Oxygen-system component","Valves, regulators and lines in oxygen service","Oxygen systems","assembly","assembly",[],["oxygen distribution"],["oxygen valve","regulator"],["MAT-NI","MAT-SS"],"oxygen-system ignition (e.g. promoted combustion, adiabatic compression)",None,None),
 ("MAT-LUBE","Lubricant","Perfluoropolyether or hydrocarbon lubricant","Aerospace specialty","liquid","liquid",["grease"],["mechanisms"],["lubricant","grease","Braycote"],[],"material combustion (oxygen compatibility dependent)",None,None),
 ("MAT-HYDFLUID","Hydraulic fluid","Hydraulic fluid","Aerospace specialty","liquid","liquid",[],["actuators"],["hydraulic fluid"],[],"material combustion",None,None),
 ("MAT-COOLANT","Coolant","Water/glycol or fluorinated coolant","Aerospace specialty","liquid","liquid",[],["thermal control loops"],["coolant","ethylene glycol"],[],"material combustion (fluid-dependent)",None,None),
 ("MAT-PROP","Propellant (representative)","Representative storable propellant","Aerospace specialty","propellant","liquid",[],["propulsion (outside cabin)"],["propellant","hydrazine"],[],"propulsion combustion (not internal cabin fire)",None,None),
 ("MAT-LABCHEM","Laboratory chemical","Generic laboratory reagent","Research fuels and chemicals","chemical","liquid",[],["experiments"],["lab chemical","reagent"],[],"material combustion (reagent-dependent)",None,None),
 ("MAT-ETHANOL","Ethanol","Ethanol","Research fuels and chemicals","liquid fuel","liquid droplet",[],["research fuel","cleaning"],["ethanol"],["MAT-METHANOL"],"material combustion","C2H5OH",None),
]
out = []
for (i, n, sci, cat, cls, form, forms, apps, al, rel, ph, comp, grade) in M:
    out.append({"id": i, "name": n, "scientific_name": sci, "category": cat, "class": cls, "default_form": form, "forms": [form] + [f for f in forms if f != form],
                "applications": apps, "aliases": al, "related_to": rel, "phenomenon": ph, "composition": comp, "grade": grade,
                "provenance": C, "user_defined": False,
                "notes": "Typical applications are illustrative possibilities, not claims of flight use on a real vehicle."})
json.dump(out, open(OUT, "w"), indent=1)
print(len(out), "materials")
