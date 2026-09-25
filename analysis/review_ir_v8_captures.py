"""Offline fixed-window hypothesis audit; no device access."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
NAMES=['stock-v7-06-double7e-20260924','stock-v7-09-payload06-20260924','stock-v7-10-payload80-20260924','stock-v8-double7e-20260924','stock-v8-double7e-repeat-20260924','stock-v8-double7e-yellow-20260924']
report={}
for name in NAMES:
 p=ROOT/'analysis/captures'/name
 b=p.with_suffix('.pod1.bin').read_bytes();m=json.loads(p.with_suffix('.scope.json').read_text());dt=float(m['preamble'].split(',')[4])
 rises=[i for i in range(1,len(b)) if b[i]&4 and not b[i-1]&4]
 falls=[i for i in range(1,len(b)) if not b[i]&16 and b[i-1]&16]
 streams=[''.join(str((b[i+round(t*1e-6/dt)]>>3)&1) for i in rises if i+round(t*1e-6/dt)<len(b)) for t in [40,50,60,70,80]]
 valid=len(rises)==101 and len(falls)==1 and len(set(streams))==1
 a={'valid_101_cell_record':valid,'clock_cells':len(rises),'bits':streams[2]}
 if valid:
  y=falls[0];a.update(yellow_start_us=(y-rises[0])*dt*1e6,last_clock_us=(rises[-1]-rises[0])*dt*1e6,cells_risen_before_yellow=sum(i<y for i in rises),payload_max_ones=max(map(len,streams[2][21:].split('0'))))
  a['fixed_c0_windows']={label:[i for i in range(94) if streams[2][i:i+8]==pattern and rises[i+7]+round(80e-6/dt)<y] for label,pattern in [('normal_msb','11000000'),('normal_lsb','00000011'),('inverted_msb','00111111'),('inverted_lsb','11111100')]}
 report[name]=a
survivors={}
for mode in report[NAMES[0]]['fixed_c0_windows']:
 survivors[mode]=sorted(set.intersection(*(set(report[n]['fixed_c0_windows'][mode]) for n in NAMES[:3])))
report['surviving_fixed_raw_windows']=survivors
report['limits']='Zero-based raw emitted cells; five lead zeros and 16 flag cells. Windows must finish by 80us after last clock before yellow. Only fixed contiguous 8-cell mappings, MSB/LSB and complement; no ASIC sampling/bit alignment proof. Rejection occurs before yellow, so this cutoff is permissive. Payload needs no conventional five-ones stuffing; flag-crossing or inverted decoding not treated as valid destuffed data.'
original=report[NAMES[0]]['bits']
mutated=original[:30]+str(1-int(original[30]))+original[31:]
report['proposed_payload_07_to_47']={
 'changed_raw_cell':30, 'payload_hex':'00470002014300000201',
 'normal_lsb_window_start':28,
 'predicted_original':f'{int(original[28:36][::-1],2):02X}',
 'predicted_mutated':f'{int(mutated[28:36][::-1],2):02X}',
 'payload_max_ones':max(map(len,mutated[21:].split('0'))),
 'limit':'Conditional fixed raw-window prediction only; byte changes may also affect framing or status.'}
output=ROOT/'analysis/captures/stock-v8-offline-review-20260924.json';output.write_text(json.dumps(report,indent=2)+'\n')
for n,a in report.items():
 if n in NAMES: print(n,{k:v for k,v in a.items() if k not in ('bits','fixed_c0_windows')})
print('survivors',survivors)
