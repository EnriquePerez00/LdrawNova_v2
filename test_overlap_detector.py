import json
import subprocess
import os
import sys

def test_mpd(mpd_path):
    env = os.environ.copy()
    env["LDRAW_DIR"] = os.path.expanduser("~/LDraw")
    res = subprocess.run(["./ldraw-agent", "validate", str(mpd_path), "--geometry"], capture_output=True, text=True, env=env)
    data = json.loads(res.stdout)
    errors = [d for d in data.get("diagnostics", []) if d.get("severity") == "error"]
    overlaps = [o for o in data.get("geometry", {}).get("overlaps", []) if o.get("body_penetration")]
    print(f"Total parts: {len(data.get('geometry', {}).get('instances', []))}")
    print(f"Errors: {len(errors)}, Overlaps with body_penetration: {len(overlaps)}")
    if errors:
        for err in errors[:5]:
            print("ERROR:", err.get("message"), err.get("sources"))
    if "optimistic_component_count" in data.get("geometry", {}):
        print("Components:", data["geometry"]["optimistic_component_count"])
    return len(errors) == 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_mpd(sys.argv[1])
