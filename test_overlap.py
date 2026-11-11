from ldraw_tools.common import load_ldraw_document
from ldraw_tools.collision import find_body_overlaps
import sys

# Test overlap between two parts
doc_text = """0 Pig test
1 29 0 -80 -20 0 0 1 0 1 0 -1 0 0 3020.dat
1 29 0 -80 20 0 0 1 0 1 0 -1 0 0 3020.dat
"""
with open("test.ldr", "w") as f:
    f.write(doc_text)

import subprocess
res = subprocess.run(["./ldraw-agent", "validate", "test.ldr", "--geometry"], capture_output=True, text=True)
print(res.stdout[:500])
