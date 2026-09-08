"""Read installed backend dependency versions and query PyPI advisories."""
import json
from pathlib import Path
from importlib import metadata
from concurrent.futures import ThreadPoolExecutor
from packaging.requirements import Requirement
import requests

root = Path(__file__).resolve().parents[1]
pending = [line.split('#',1)[0].strip() for line in (root/'backend/requirements.txt').read_text().splitlines() if line.strip() and not line.startswith('#')]
pending += ['python-multipart', 'requests', 'pywebview']
versions = {}
missing = []
while pending:
    req = Requirement(pending.pop())
    name = req.name.lower().replace('_','-')
    if name in versions or name in missing:continue
    try:dist=metadata.distribution(name)
    except metadata.PackageNotFoundError:missing.append(name);continue
    versions[name]=dist.version
    for dep in dist.requires or []:
        parsed=Requirement(dep)
        if parsed.marker is None or parsed.marker.evaluate():pending.append(dep)

def query(item):
    name,version=item
    try:
        response=requests.get(f'https://pypi.org/pypi/{name}/{version}/json',timeout=20)
        response.raise_for_status()
        return {'name':name,'version':version,'vulnerabilities':[{'id':v['id'],'aliases':v.get('aliases'),'fixed_in':v.get('fixed_in'),'link':v.get('link'),'summary':v.get('summary') or v.get('details','')[:500]} for v in response.json().get('vulnerabilities',[])]}
    except Exception as exc:return {'name':name,'version':version,'error':str(exc)}
with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(query,sorted(versions.items())))
out={'scope':'Installed dependency closure for backend requirements plus multipart, requests and desktop pywebview; current machine, not a locked release environment. Optional extras may be absent.', 'missing':missing,'packages':results}
(root/'docs/audit-python-dependencies.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'packages_checked':len(results),'missing':missing,'advisories':[r for r in results if r.get('vulnerabilities')],'errors':[r for r in results if r.get('error')]},indent=2))
