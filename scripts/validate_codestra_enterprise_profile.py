#!/usr/bin/env python3
import json,os,pathlib,sys
REQ={"codestra","moneybee","beyvra","breero","larim-a","transportation","booked4seasons","social","klyrow","telnexa","kyqra","restaurant","provisioning"}; HOST='otel.codestra.media'
def fail(m): print('ERROR: '+m,file=sys.stderr); raise SystemExit(1)
p=pathlib.Path('codestra/enterprise-profile.v1.json')
if not p.exists(): fail('missing enterprise profile')
d=json.loads(p.read_text())
if d.get('canonicalHostname')!=HOST: fail('wrong canonical hostname')
if d.get('schemaVersion')!='1.0' or d.get('status')!='SOURCE_PREPARED_NOT_DEPLOYED': fail('invalid schema/status')
b=set(d.get('businessScope',[])); miss=REQ-b
if miss: fail('missing businesses: '+', '.join(sorted(miss)))
if len(b)!=len(d.get('businessScope',[])) or not d.get('features'): fail('invalid business/features definition')
if d.get('exposure')=='public_native': fail('native service may not be public')
print('Codestra enterprise profile validation PASS: '+os.environ.get('GITHUB_REPOSITORY','telemetry'))
