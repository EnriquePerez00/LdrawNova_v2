with open("output/pig_sculpture/generate_hd.py") as f:
    code = f.read()

# At [-30, -48, -70] we had tile 3070b. A tile has NO top studs, so a plate 3024 at -56 cannot connect to it!
# If we replace tile 3070b at [-30, -48, -70] with a plate 3024 at [-30, -48, -70]:
# Then the ear plate 3024 at [-30, -56, -70] connects directly to it!
old_temple_tile = """        # Rear temple tiles 1x1 Pink at rear stud:
        self.add_part(sub_head, "3070b", COLOR_PINK, [-30.0, -48.0, -70.0], ROT_ID, "Left rear temple tile 1x1")
        self.add_part(sub_head, "3070b", COLOR_PINK, [30.0, -48.0, -70.0], ROT_ID, "Right rear temple tile 1x1")"""

new_temple_plate = """        # Rear temple plates 1x1 Pink at rear stud (stud male facing up):
        self.add_part(sub_head, "3024", COLOR_PINK, [-30.0, -48.0, -70.0], ROT_ID, "Left rear temple plate 1x1")
        self.add_part(sub_head, "3024", COLOR_PINK, [30.0, -48.0, -70.0], ROT_ID, "Right rear temple plate 1x1")"""
code = code.replace(old_temple_tile, new_temple_plate)

# And tail clip 4085c: at Z = 60, Y = -32 (connects to rear torso brick top/bottom):
# Rear of torso is at Z in [40, 60] (center Z = 50).
# Studs of rear torso brick at Z=50 are at Z=50.
# A plate 1x1 with clip 4085c at [0, -32, 50] connects to the rear torso brick!
# And clip faces rearward (+Z) to hold the tail spiral:
code = code.replace("[0.0, -32.0, 70.0]", "[0.0, -32.0, 50.0]")
code = code.replace("[0.0, -32.0, 78.0]", "[0.0, -32.0, 64.0]")

with open("output/pig_sculpture/generate_hd.py", "w") as f:
    f.write(code)

print("Final 4 parts adjusted")
