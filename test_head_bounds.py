import json, subprocess, os
env = os.environ.copy()
env['LDRAW_DIR'] = os.path.expanduser('~/LDraw')
res = subprocess.run(['./ldraw-agent', 'validate', 'output/pig_sculpture/pig_sculpture.mpd', '--geometry'], capture_output=True, text=True, env=env)
d = json.loads(res.stdout)
for err in d.get('diagnostics', []):
    if err.get('severity') == 'error':
        print(err['message'], err['sources'])
