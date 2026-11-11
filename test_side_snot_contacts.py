import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')
res = subprocess.run(['./ldraw-agent', 'validate', 'test_snot_side.mpd', '--geometry'], capture_output=True, text=True, env=env)
d = json.loads(res.stdout)
for inst in d['geometry']['instances']:
    print(inst['part'], inst['position'], inst['bounds'])
print('Contacts:', d['geometry']['contact_count'])
