"""Reproduce the saved v7 C0 comparison from POD1 captures; no hardware I/O."""
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
files=['stock-v7-01-baseline-repeat-20260924','stock-v7-06-double7e-20260924','stock-v7-01-final-20260924']
report={}
for name in files:
 p=root/'analysis/captures'/name
 raw=p.with_suffix('.pod1.bin').read_bytes();meta=json.loads(p.with_suffix('.scope.json').read_text());dt=float(meta['preamble'].split(',')[4]);r=[i for i in range(1,len(raw)) if raw[i]&4 and not raw[i-1]&4];fall=[i for i in range(1,len(raw)) if not raw[i]&16 and raw[i-1]&16]
 streams={str(us):''.join(str((raw[i+round(us*1e-6/dt)]>>3)&1) for i in r) for us in [40,50,60,70,80]}
 assert len(set(streams.values()))==1
 bits=streams['60'];flags=2 if '06-' in name else 1;start=5+8*flags;payload=bits[start:]
 expected=''.join(f'{v:08b}' for v in bytes.fromhex('00070002014300000201'))
 assert bits=='00000'+'01111110'*flags+expected
 def unstuff(stream,counted):
  output='';run=0;removed=[];violations=[]
  for i,c in enumerate(stream):
   if run==5:
    if c==counted:violations.append(i);break
    removed.append(i);run=0;continue
   output+=c;run=run+1 if c==counted else 0
  return {'bits':output,'removed_payload_indices':removed,'first_violation_payload_index':violations[0] if violations else None}
 windows={}
 for key,target in [('normal_msb','11000000'),('normal_lsb','00000011'),('inverted_msb','00111111'),('inverted_lsb','11111100')]:
  windows[key]=[{'start_cell_zero_based':i,'end_cell_zero_based':i+7,'payload_relative_start':i-start,'end_sample_from_first_clock_us':round((r[i+7]-r[0])*dt*1e6+60,1),'ends_before_yellow':r[i+7]+round(60e-6/dt)<fall[0]} for i in range(len(bits)-7) if bits[i:i+8]==target]
 report[name]={'index_convention':'zero-based emitted clock cell; five lead cells; flags excluded from payload destuffing','data_sampling_offsets_checked_us':[40,50,60,70,80],'bits':bits,'clock_cells':len(r),'payload_start_cell':start,'payload_max_consecutive_ones':max(map(len,payload.split('0'))),'payload_max_consecutive_zeros':max(map(len,payload.split('1'))),'normal_destuff':unstuff(payload,'1'),'complementary_destuff_on_observed_levels':unstuff(payload,'0'),'aligned_payload_bytes_msb':[f'{int(payload[i:i+8],2):02X}' for i in range(0,len(payload),8)],'c0_sliding_windows':windows,'yellow_start_from_first_clock_us':round((fall[0]-r[0])*dt*1e6,1),'last_clock_from_first_clock_us':round((r[-1]-r[0])*dt*1e6,1),'clock_rises_before_yellow':sum(i<fall[0] for i in r)}
original=report['stock-v7-06-double7e-20260924']['bits']
mutated=original[:36]+'0'+original[37:]
assert original[36]=='1'
assert int(original[35:43],2)==0xC0
assert int(mutated[35:43],2)==0x80
assert max(map(len,mutated[21:].split('0')))<5
report['proposed_07_to_06']={
    'changed_payload_byte_zero_based':1,
    'changed_payload_byte_bit':0,
    'changed_emitted_cell_zero_based':36,
    'original_window_cells_35_through_42':'C0',
    'mutated_window_cells_35_through_42':'80',
    'stuff_bits_before_and_after':0,
    'interpretation':'Conditional shifted-window prediction, not ASIC decode identification',
}
sys.path.insert(0,str(root/'analysis/rom_exerciser'))
import stock_context_v7 as v7
from test_stock_context_v7 import _run
image,symbols,_=v7.build_image()
_,_,events=_run(image,symbols,[0x8E],descriptor=bytes.fromhex('0600e4fd0000'),data=b'\xc0')
status=[e for e in events if e[:2]==('in',0x4B)][-1]
terminal=[e for e in events if e[:2]==('in',0x4E)][-1]
yellow=[e for e in events if e[:2]==('out',0x2A)][1]
delay=yellow[3]-status[3]
report['conditional_emulator_timing']={
    'status_to_yellow_falling_tstates':delay,
    'terminal_ini_to_yellow_falling_tstates':yellow[3]-terminal[3],
    'clock_hz':3686400,
    'status_to_yellow_falling_us':delay/3.6864,
    'estimated_status_from_first_clock_us':8262.4-delay/3.6864,
    'limitations':'Exact emulator fixture only; not an observed ASIC sampling timestamp. Assumes CPU clock, no extra IRQ/wait-state delays, and corresponding GPIO edge timing.',
}
(root/'analysis/captures/stock-v7-c0-bitstream-analysis-20260924.json').write_text(json.dumps(report,indent=2)+'\n')
for name,a in report.items():
 if 'clock_cells' not in a: continue
 print(name,'payloadstart',a['payload_start_cell'],'normal removed',a['normal_destuff']['removed_payload_indices'],'complement violation',a['complementary_destuff_on_observed_levels']['first_violation_payload_index'],'yellow',a['yellow_start_from_first_clock_us'],'clocks_before',a['clock_rises_before_yellow']);print(a['c0_sliding_windows'])
