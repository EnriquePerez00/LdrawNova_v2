with open("output/pig_sculpture/generate_hd.py") as f:
    code = f.read()

# 1. Place eye tiles 98138 at exact stud coordinates:
# Left temple plate 1x2 at [-30, -40, -80] with ROT_Y_90 has studs at [-30, -40, -90] and [-30, -40, -70].
# So eye tile at [-30, -48, -90]!
# Right eye tile at [30, -48, -90]!
# Rear temple tile 1x1 (3070b) at [-30, -48, -70] and [30, -48, -70]!
old_eyes = """        # Expressive Black Round Eye Tiles 1x1 (`98138`) resting on temple plates:
        self.add_part(sub_head, "98138", COLOR_BLACK, [-30.0, -48.0, -80.0], ROT_ID, "Left eye pupil round tile 1x1")
        self.add_part(sub_head, "98138", COLOR_BLACK, [30.0, -48.0, -80.0], ROT_ID, "Right eye pupil round tile 1x1")"""

new_eyes = """        # Expressive Black Round Eye Tiles 1x1 (`98138`) on front stud of temple plates:
        self.add_part(sub_head, "98138", COLOR_BLACK, [-30.0, -48.0, -90.0], ROT_ID, "Left eye pupil round tile 1x1")
        self.add_part(sub_head, "98138", COLOR_BLACK, [30.0, -48.0, -90.0], ROT_ID, "Right eye pupil round tile 1x1")
        # Rear temple tiles 1x1 Pink at rear stud:
        self.add_part(sub_head, "3070b", COLOR_PINK, [-30.0, -48.0, -70.0], ROT_ID, "Left rear temple tile 1x1")
        self.add_part(sub_head, "3070b", COLOR_PINK, [30.0, -48.0, -70.0], ROT_ID, "Right rear temple tile 1x1")"""
code = code.replace(old_eyes, new_eyes)

# 2. Forehead and crown:
# Upper cranium brick 2x2 is at Y = -64, Z = -80.
# Its top (Y=-64) has 4 studs: [-10, -64, -90], [10, -64, -90], [-10, -64, -70], [10, -64, -70].
# Forehead brow curved slope 15068 at Y = -64, Z = -80 is already sitting right there!
# Remove redundant crown tile 3069b which was at Y=-72 (overlapping the slope):
old_crown = """        # Crown tile 1x2 Pink:
        self.add_part(sub_head, "3069b", COLOR_PINK, [0.0, -72.0, -80.0], ROT_ID, "Cranial crown tile 1x2")"""
code = code.replace(old_crown, "")

# 3. Ear base plates: placed on rear temple tile at Y = -56, Z = -70:
old_ears = """        # Ear anchor plates 1x1 Pink at Y = -72, Z = -80:
        self.add_part(sub_head, "3024", COLOR_PINK, [-30.0, -72.0, -80.0], ROT_ID, "Left ear base plate 1x1")
        self.add_part(sub_head, "3024", COLOR_PINK, [30.0, -72.0, -80.0], ROT_ID, "Right ear base plate 1x1")"""
code = code.replace(old_ears, "")

# 4. Chin plate: Snout lower brick is at Y = -32, Z = -110. Sockets at bottom (Y = -8).
# Chin plate 1x2 at Y = -8, Z = -110 connects directly to snout brick sockets!
code = code.replace("[0.0, -24.0, -110.0]", "[0.0, -8.0, -110.0]")

# 5. Tail horn 89522: clip is at [0, -32, 70], facing +Z.
# Horn spiral plugs at Z = 78:
code = code.replace("[0.0, -32.0, 90.0]", "[0.0, -32.0, 78.0]")
code = code.replace("""        self.add_part(sub_tail, "3024", COLOR_PINK, [0.0, -24.0, 70.0], ROT_ID, "Tail base tie plate 1x1")""", "")

with open("output/pig_sculpture/generate_hd.py", "w") as f:
    f.write(code)

print("Replacement script executed")
