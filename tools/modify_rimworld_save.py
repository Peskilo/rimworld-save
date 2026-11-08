#!/usr/bin/env python3
"""Create a separate edited RimWorld 1.5 save from the repository save."""
# This file is run by the repository workflow after each relevant push.
import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCE = Path("выживчики.rws")
OUTPUT = Path("выживчики_Дом_Александр_Тирэйн.rws")
TICK = "156779"

if not SOURCE.exists():
    raise SystemExit(f"Missing source save: {SOURCE}")

tree = ET.parse(SOURCE)
root = tree.getroot()
game = root.find("game")
if game is None:
    raise SystemExit("Invalid RimWorld save: <game> not found")

maps = game.find("maps")
if maps is None or not list(maps):
    raise SystemExit("No map found")
map_node = list(maps)[0]
things = map_node.find("things")
if things is None:
    raise SystemExit("Map has no <things> list")

def get_text(node, tag, default=""):
    child = node.find(tag)
    return child.text if child is not None and child.text is not None else default

def in_footprint(pos_text):
    m = re.search(r"\((\d+),\s*0,\s*(\d+)\)", pos_text or "")
    if not m:
        return False
    x, z = int(m.group(1)), int(m.group(2))
    return 125 <= x <= 174 and 5 <= z <= 44

# Keep Kain's assigned bed but relocate it into the new barracks.
# Remove the old small structures, nearby vegetation and debris.
removed = {"buildings": 0, "plants": 0, "filth": 0, "hostiles": 0, "turrets": 0}
for thing in list(things):
    if thing.tag != "thing":
        continue
    thing_id = get_text(thing, "id")
    def_name = get_text(thing, "def")
    cls = thing.get("Class", "")
    pos = get_text(thing, "pos")

    if thing_id == "Bed11337":
        thing.find("pos").text = "(127, 0, 22)"
        continue

    if def_name == "AncientSecurityTurret":
        things.remove(thing)
        removed["turrets"] += 1
        continue

    if cls == "Pawn" and get_text(thing, "faction") == "Faction_10":
        things.remove(thing)
        removed["hostiles"] += 1
        continue

    if in_footprint(pos) and cls.startswith("Building"):
        things.remove(thing)
        removed["buildings"] += 1
        continue
    if in_footprint(pos) and cls == "Plant":
        things.remove(thing)
        removed["plants"] += 1
        continue
    if in_footprint(pos) and cls == "Filth":
        things.remove(thing)
        removed["filth"] += 1
        continue

# Find Jack's pawn as a template and clone it as Alexander.
template = next((t for t in things if t.tag == "thing" and t.get("Class") == "Pawn"
                 and get_text(t, "id") == "Human1038"), None)
if template is None:
    raise SystemExit("Could not find template colonist Human1038")
doctor = copy.deepcopy(template)

# Give every thing embedded in the cloned pawn a unique load ID.
id_nodes = [e for e in doctor.iter("id") if e.text]
id_map = {}
for i, element in enumerate(id_nodes):
    old = element.text
    if i == 0:
        new = "Human50000"
    else:
        prefix = re.sub(r"\d+$", "", old)
        new = f"{prefix}{52000 + i}"
    id_map[old] = new
id_map["Thing_Human1038"] = "Thing_Human50000"
id_map["Human1038"] = "Human50000"

for element in doctor.iter():
    if element.text:
        value = element.text
        for old, new in sorted(id_map.items(), key=lambda pair: len(pair[0]), reverse=True):
            value = value.replace(old, new)
        element.text = value
    if element.tail:
        value = element.tail
        for old, new in sorted(id_map.items(), key=lambda pair: len(pair[0]), reverse=True):
            value = value.replace(old, new)
        element.tail = value

doctor.find("id").text = "Human50000"
doctor.find("pos").text = "(162, 0, 28)"
doctor.find("faction").text = "Faction_14"
doctor.find("kindDef").text = "Colonist"
doctor.find("spawnedTick").text = TICK
doctor.find("gender").text = "Male"

name = doctor.find("name")
if name is None:
    name = ET.SubElement(doctor, "name", {"Class": "NameTriple"})
for key, value in (("first", "Александр"), ("nick", "Спокойный"), ("last", "Тирэйн")):
    child = name.find(key)
    if child is None:
        child = ET.SubElement(name, key)
    child.text = value

story = doctor.find("story")
traits = story.find("traits") if story is not None else None
all_traits = traits.find("allTraits") if traits is not None else None
if all_traits is not None:
    for child in list(all_traits):
        all_traits.remove(child)
    for trait_name in ("Kind", "Steadfast"):
        li = ET.SubElement(all_traits, "li")
        ET.SubElement(li, "def").text = trait_name
        ET.SubElement(li, "sourceGene").text = "null"
        ET.SubElement(li, "suppressedBy").text = "null"

skills = doctor.find("skills")
skill_list = skills.find("skills") if skills is not None else None
def set_skill(skill_name, level, passion):
    if skill_list is None:
        return
    entry = next((li for li in skill_list.findall("li") if get_text(li, "def") == skill_name), None)
    if entry is None:
        entry = ET.SubElement(skill_list, "li")
        ET.SubElement(entry, "def").text = skill_name
    level_node = entry.find("level")
    if level_node is None:
        level_node = ET.SubElement(entry, "level")
    level_node.text = str(level)
    passion_node = entry.find("passion")
    if passion_node is None:
        passion_node = ET.SubElement(entry, "passion")
    passion_node.text = passion
    for tag in ("xpSinceLastLevel", "xpSinceMidnight"):
        xp = entry.find(tag)
        if xp is not None:
            xp.text = "0"

set_skill("Medicine", 18, "Major")
set_skill("Intellectual", 12, "Major")
set_skill("Social", 8, "Minor")
set_skill("Shooting", 6, "Minor")

# Prioritize firefighting, patient care and doctor work.
work_settings = doctor.find("workSettings")
priorities = work_settings.find("priorities") if work_settings is not None else None
vals = priorities.find("vals") if priorities is not None else None
if vals is not None:
    values = vals.findall("li")
    if len(values) > 2:
        values[2].text = "1"

# Unique numeric job IDs for the copied pawn's active job state.
next_job = 70000
for element in doctor.iter("loadID"):
    if element.text and element.text.isdigit():
        element.text = str(next_job)
        next_job += 1

# Construction helpers.
next_thing = 51000
added = []
def add_thing(class_name, def_name, prefix, x, z, fields):
    global next_thing
    thing = ET.Element("thing", {"Class": class_name})
    ET.SubElement(thing, "def").text = def_name
    ET.SubElement(thing, "id").text = f"{prefix}{next_thing}"
    next_thing += 1
    ET.SubElement(thing, "map").text = "0"
    ET.SubElement(thing, "pos").text = f"({x}, 0, {z})"
    for tag, value in fields:
        child = ET.SubElement(thing, tag)
        child.text = value
    added.append(thing)
    return thing

base_fields = [
    ("health", "300"), ("stuff", "BlocksMarble"), ("faction", "Faction_14"),
    ("questTags", ""), ("spawnedTick", TICK), ("lastUser", "null")
]
# Outer 50x40 footprint, plus room partitions.
wall_cells = set()
def wall(x, z):
    wall_cells.add((x, z))

for x in range(125, 175):
    if x != 150:
        wall(x, 5)
    wall(x, 44)
for z in range(5, 45):
    wall(125, z)
    wall(174, z)
for x in range(126, 174):
    if x not in (132, 145, 164):
        wall(x, 18)
for z in range(19, 44):
    if z not in (27, 36):
        wall(137, z)
        wall(156, z)
for x in range(138, 156):
    if x != 146:
        wall(x, 32)

for x, z in sorted(wall_cells):
    add_thing("Building", "Wall", "Wall", x, z, base_fields)

def add_door(x, z):
    add_thing("Building_Door", "Door", "Door", x, z, [
        ("rot", "1"), ("health", "150"), ("stuff", "WoodLog"),
        ("faction", "Faction_14"), ("questTags", ""), ("spawnedTick", TICK),
        ("lastFriendlyTouchTick", "-9999"), ("approachingPawn", "null")
    ])
for x, z in ((150,5),(132,18),(145,18),(164,18),(137,27),(156,27),(137,36),(156,36),(146,32)):
    add_door(x, z)

def add_bed(x, z, medical=False, assigned=None):
    bed = add_thing("Building_Bed", "Bed", "Bed", x, z, [
        ("rot", "1"), ("health", "200"), ("stuff", "BlocksMarble"),
        ("faction", "Faction_14"), ("questTags", ""), ("spawnedTick", TICK)
    ])
    assigned_node = ET.SubElement(bed, "assignedPawns")
    if assigned:
        ET.SubElement(assigned_node, "li").text = assigned
    ET.SubElement(bed, "uninstalledAssignedPawns")
    ET.SubElement(bed, "quality").text = "Normal"
    ET.SubElement(bed, "taleRef", {"IsNull": "True"})
    ET.SubElement(bed, "alreadySetDefaultMed").text = "True"
    if medical:
        ET.SubElement(bed, "medical").text = "True"

def add_dresser(x, z):
    add_thing("Building", "Dresser", "Dresser", x, z, [
        ("rot", "1"), ("health", "180"), ("stuff", "WoodLog"),
        ("faction", "Faction_14"), ("questTags", ""), ("spawnedTick", TICK),
        ("quality", "Normal")
    ])

def add_worktable(def_name, x, z, fueled=False):
    table = add_thing("Building_WorkTable", def_name, def_name, x, z, [
        ("rot", "1"), ("health", "200"), ("stuff", "WoodLog"),
        ("faction", "Faction_14"), ("questTags", ""), ("spawnedTick", TICK)
    ])
    if fueled:
        ET.SubElement(table, "fuel").text = "50"
        ET.SubElement(table, "allowAutoRefuel").text = "True"
    bill_stack = ET.SubElement(table, "billStack")
    ET.SubElement(bill_stack, "bills")

def add_dining_table(x, z):
    add_thing("Building_Table", "Table2x2c", "Table2x2c", x, z, [
        ("rot", "0"), ("health", "200"), ("stuff", "WoodLog"),
        ("faction", "Faction_14"), ("questTags", ""), ("spawnedTick", TICK),
        ("quality", "Normal")
    ])

def add_shelf(x, z):
    add_thing("Building_Storage", "Shelf", "Shelf", x, z, [
        ("rot", "1"), ("health", "200"), ("stuff", "WoodLog"),
        ("faction", "Faction_14"), ("questTags", ""), ("spawnedTick", TICK)
    ])

# Barracks: Kain's original assigned bed was moved here; add three more beds.
add_bed(131, 22)
add_bed(127, 28)
add_bed(131, 28)
add_dresser(134, 22)
add_dresser(134, 28)

# Workshop, research area, kitchen and dining room.
add_worktable("TableButcher", 142, 24)
add_worktable("ResearchBench", 149, 24)
add_worktable("FueledStove", 140, 37, fueled=True)
add_dining_table(149, 37)

# Large storage room.
for x, z in ((130,8),(138,8),(146,8),(154,8),(162,8),(169,8)):
    add_shelf(x, z)

# Medical room replacing the former cold-storage room.
add_bed(160, 23, medical=True)
add_bed(165, 23, medical=True, assigned="Thing_Human50000")
add_bed(160, 35, medical=True)
add_bed(165, 35, medical=True)
add_shelf(170, 39)

for thing in added:
    things.append(thing)
things.append(doctor)

# Unlock practical infrastructure and medical research, without combat or drug branches.
research_manager = game.find("researchManager")
progress = research_manager.find("progress") if research_manager is not None else None
if progress is None:
    raise SystemExit("Research progress not found")
keys_node = progress.find("keys")
values_node = progress.find("values")
if keys_node is None or values_node is None:
    raise SystemExit("Research key/value arrays not found")
research_keys = [li.text for li in keys_node.findall("li")]
research_values = values_node.findall("li")
research_targets = {
    "ComplexFurniture", "Electricity", "Batteries", "SolarPanels", "AirConditioning",
    "Autodoors", "Hydroponics", "GeothermalPower", "SterileMaterials", "HospitalBed",
    "MedicineProduction", "DeepDrilling", "GroundPenetratingScanner", "MultiAnalyzer",
    "Fabrication", "Bionics", "Prosthetics", "VitalsMonitor", "Biosculpting",
    "Bioregeneration", "NutrientPaste", "PassiveCooler", "WatermillGenerator"
}
completed = []
for index, key in enumerate(research_keys):
    if key in research_targets and index < len(research_values):
        research_values[index].text = "999999"
        completed.append(key)

# Add a visible arrival letter and a chronicle note.
letter_stack = game.find("letterStack")
letters = letter_stack.find("letters") if letter_stack is not None else None
if letters is not None:
    letter = ET.SubElement(letters, "li", {"Class": "StandardLetter"})
    ET.SubElement(letter, "def").text = "Joiner"
    ET.SubElement(letter, "label").text = "Александр «Спокойный» Тирэйн присоединился к колонии"
    look_targets = ET.SubElement(letter, "lookTargets")
    targets = ET.SubElement(look_targets, "targets")
    ET.SubElement(targets, "li").text = "Thing_Human50000"
    ET.SubElement(letter, "relatedFaction").text = "null"
    ET.SubElement(letter, "arrivalTick").text = TICK
    ET.SubElement(letter, "text").text = "Александр «Спокойный» Тирэйн прибыл к поселению. Он опытный врач и готов помогать колонии."
    ET.SubElement(letter, "quest").text = "null"
    ET.SubElement(letter, "hyperlinkThingDefs", {"IsNull": "True"})
    ET.SubElement(letter, "hyperlinkHediffDefs", {"IsNull": "True"})

history = game.find("history")
archive = history.find("archive/archivables") if history is not None else None
if archive is not None:
    entry = ET.SubElement(archive, "li", {"Class": "ArchivedDialog"})
    ET.SubElement(entry, "text").text = "К колонии присоединился Александр «Спокойный» Тирэйн — врач с медицинским навыком 18. Для него подготовлено место в медицинском крыле."
    ET.SubElement(entry, "relatedFaction").text = "null"

# Update ID counters and focus the camera on the new home.
unique = game.find("uniqueIDsManager")
if unique is not None:
    next_thing = unique.find("nextThingID")
    if next_thing is not None:
        next_thing.text = str(max(52000, next_thing + 100 if False else 52000 + len(added) + 100))
    next_job = unique.find("nextJobID")
    if next_job is not None:
        next_job.text = str(max(80000, next_job + 100 if False else 80000 + 100))
camera = game.find("cameraMap")
cam_pos = camera.find("camRootPos") if camera is not None else None
if cam_pos is not None:
    cam_pos.text = "(150.0, 16.4, 25.0)"

# Ensure the new colonist and structures have unique IDs, then write a separate save.
all_ids = [get_text(t, "id") for t in things.findall("thing")]
if len(all_ids) != len(set(all_ids)):
    raise SystemExit("Duplicate thing IDs detected")
if not any(get_text(t, "id") == "Human50000" for t in things.findall("thing")):
    raise SystemExit("New doctor was not added to map")

tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)
# Re-open the output to ensure it is well-formed XML.
ET.parse(OUTPUT)
print(f"Created {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
print(f"New walls: {len(wall_cells)}; doors: 9; new beds: 7; doctor: Alexander 'Спокойный' Тирэйн")
print(f"Removed from the map: {removed}")
print(f"Research completed: {', '.join(completed)}")
