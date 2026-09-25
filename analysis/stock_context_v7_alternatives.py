"""Offline GPIO phase and handheld-prelude evidence for v7 alternatives."""
import json
from pathlib import Path
from scope_ir_decode import destuff_checked
ROOT=Path(__file__).resolve().parent.parent
names=['stock-v7-06-double7e-20260924','stock-v7-09-payload06-20260924','stock-v7-10-payload80-20260924']
report={}
for name in names:
    p=ROOT/'analysis/captures'/name
    raw=p.with_suffix('.pod1.bin').read_bytes()
    dt=float(json.loads(p.with_suffix('.scope.json').read_text())['preamble'].split(',')[4])
    rises=[i for i in range(1,len(raw)) if raw[i]&4 and not raw[i-1]&4]
    samples={str(us):''.join(str((raw[i+round(us*1e-6/dt)]>>3)&1) for i in rises) for us in [0,10,20,30,40,60,80,100,115]}
    report[name]={'offsets_us_to_bits':samples,'ones_per_offset':{k:v.count('1') for k,v in samples.items()},'meaning':'D3 sampled relative to D2 GPIO rise only; ASIC optical polarity and sampling edge unknown'}
p=ROOT/'analysis/captures'/names[0]
raw=p.with_suffix('.pod1.bin').read_bytes()
hr=[i for i in range(1,len(raw)) if raw[i]&2 and not raw[i-1]&2]
groups=[]
for i in hr:
    if not groups or (i-groups[-1][-1])*dt>.0004: groups.append([])
    groups[-1].append(i)
bursts=[]
for group in groups:
    if len(group)<8: continue
    bits=''.join(str(raw[i]&1) for i in group)
    flag=bits.find('10000001')
    decoded,valid,error=destuff_checked(bits[flag+8:]) if flag>=0 else ('',False,'no flag')
    bursts.append({'clock_edges':len(group),'D0_at_D1_rise':bits,'flag_index':flag,'destuffed_body':decoded,'valid_stuffing':valid,'error':error})
report['handheld_before_original_reply']={'bursts':bursts,'bit_reverse_03':'C0','meaning':'03->C0 is only a numerical match, not proof of self-reception or bit order'}
(ROOT/'analysis/captures/stock-v7-alternatives-analysis-20260924.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v.get('ones_per_offset',v) for k,v in report.items()},indent=2))
