"""Release gates for the post-return active-buffer snapshot."""
import hashlib
import json
import pathlib
import sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'rom_exerciser'))
import stock_context_v7 as v7
import stock_context_v8 as v8
from test_stock_context_v7 import _run, _registers
from test_stock_context_v6 import _lcd_text

@pytest.mark.parametrize('statuses', [[0xCA],[0x8E],[1,0x8A],[1,0x8E],[1,1,1,0x8A],[0],[1,1,0x02]])
def test_receive_registers_io_and_marker_timing_identical(statuses):
    old,os,_=v7.build_image(); new,ns,_=v8.build_image()
    # At the stock-return boundary before either diagnostic prints.
    a,am,ae=_run(old,os,statuses,stop=os['rx_wrapper']+6)
    b,bm,be=_run(new,ns,statuses,stop=ns['rx_wrapper']+6)
    assert _registers(a)==_registers(b)
    assert ae==be
    assert am[0x9000:0x9010]==bm[0x9000:0x9010]
    _,_,ae=_run(old,os,statuses)
    _,_,be=_run(new,ns,statuses)
    # Includes LCD setup until output starts: compare all link and marker I/O.
    ports={0x4A,0x4B,0x4C,0x4D,0x4E,0x4F,0x2A}
    assert [e for e in ae if e[1] in ports]==[e for e in be if e[1] in ports]

@pytest.mark.parametrize('statuses,data,sample,terminal,ordinary',[
    ([0xCA],b'\xA5',[None,None],None,0),
    ([0x8E],b'\xC0',['C0',None],'C0',0),
    ([1,0x8A],b'\x5A',['5A',None],None,1),
    ([1,0x8E],b'\x12\x34',['12','34'],'34',1),
    ([1,1,0x8A],b'\x12\x34',['12','34'],None,2),
    ([1,1,1,0x8A],b'\x11\x22\x33',['11','22'],None,3),
    ([1,1,0x8E],b'\x11\x22\x33',['11','22'],'33',2),
])
def test_reads_and_invalid_slots(statuses,data,sample,terminal,ordinary):
    image,symbols,_=v8.build_image()
    _,_,events=_run(image,symbols,statuses,descriptor=bytes.fromhex('0600e4fd0000'),data=data)
    text=_lcd_text(events)
    assert len(text)==40 and text.startswith('R8I') and text[20]=='X'
    record=v8.decode_readout(text)['terminal_record']
    assert record['buffer_snapshot_consistent']
    assert record['buffer_sample_bytes']==sample
    assert record['terminal_byte']==terminal
    assert record['active_descriptor_ordinary_reads']==ordinary
    assert record['active_descriptor_bytes_not_shown']==max(0,ordinary+int(terminal is not None)-2)
    assert 'saved_bc' not in record

@pytest.mark.parametrize('value',[0,0x7E,0x81,0xFF])
def test_ordinary_byte_values_not_constant(value):
    image,symbols,_=v8.build_image()
    _,_,events=_run(image,symbols,[1,0x8A],data=bytes([value]))
    assert v8.decode_readout(_lcd_text(events))['terminal_record']['buffer_sample_bytes']==[f'{value:02X}',None]

def test_active_descriptor_not_chain_head():
    image,symbols,_=v8.build_image()
    _,_,events=_run(image,symbols,[1,1,1,1,0x8A],
        descriptor=bytes.fromhex('03000090 05001090 00000000'),data=bytes.fromhex('1122335A'))
    r=v8.decode_readout(_lcd_text(events))['terminal_record']
    assert r['descriptor_address']=='8004'
    assert r['buffer_sample_bytes']==['5A',None]
    assert r['active_descriptor_ordinary_reads']==1

@pytest.mark.parametrize('statuses,expected', [([0xCA],[None,None]),([1,0x8A],['A5',None])])
def test_256_byte_descriptor(statuses,expected):
    image,symbols,_=v8.build_image()
    _,_,events=_run(image,symbols,statuses,descriptor=bytes.fromhex('000100900000'))
    r=v8.decode_readout(_lcd_text(events))['terminal_record']
    assert r['descriptor_length']==256
    assert r['buffer_sample_bytes']==expected

@pytest.mark.parametrize('statuses,descriptor', [([0],bytes.fromhex('060000900000')),([0xCA],bytes(6)),([1,1,2],bytes.fromhex('060000900000'))])
def test_no_snapshot_on_non_ec(statuses,descriptor):
    image,symbols,_=v8.build_image()
    _,_,events=_run(image,symbols,statuses,descriptor=descriptor)
    text=_lcd_text(events)
    assert len(text)==7
    assert v8.decode_readout(text)['terminal_record'] is None

def test_guards_and_patch_scope(tmp_path,monkeypatch):
    image,symbols,stock=v8.build_image()
    assert symbols['end']<=v8.v3.CODE_END+1
    allowed=set(range(v8.v3.CODE_ORG,v8.v3.CODE_END+1))
    for address,original in [(v8.v3.RX_CALL_SITE,v8.v3.RX_CALL_BYTES),(v8.v3.INIT_SITE,v8.v3.INIT_BYTES),(v8.STATUS_HOOK_SITE,v8.STATUS_HOOK_BYTES)]:
        allowed.update(range(address,address+len(original)))
    assert {i for i,(a,b) in enumerate(zip(stock,image)) if a!=b}<=allowed
    for address,original in v8.v5.RESET_SITES:
        assert image[address:address+len(original)]==original
    path=tmp_path/'bad.bin'
    for address in [0x1234,v8.STATUS_HOOK_SITE,v8.v3.CODE_END]:
        bad=bytearray(stock);bad[address]^=1;path.write_bytes(bad)
        with monkeypatch.context() as patch:
            if address!=0x1234:patch.setattr(v8.v3,'STOCK_SHA256',hashlib.sha256(bad).hexdigest())
            with pytest.raises(ValueError):v8.build_image(path)

def test_decoder_rejects_mismatch_and_marks_inconsistent_snapshot():
    for text in ['R7IEC29:8A000600E4FD X0EFEE5FD5A00060005','R8IEC29']:
        with pytest.raises(ValueError):v8.decode_readout(text)
    r=v8.decode_readout('R8IEC29:8A000600E4FD X0EFEEBFD5A00060005')['terminal_record']
    assert not r['buffer_snapshot_consistent']
    assert r['buffer_sample_bytes']==[None,None]


def test_one_byte_descriptor_terminal_sample():
    image,symbols,_=v8.build_image()
    _,_,events=_run(image,symbols,[0x8E],descriptor=bytes.fromhex('010000900000'),data=b'\x81')
    r=v8.decode_readout(_lcd_text(events))['terminal_record']
    assert r['buffer_snapshot_consistent']
    assert r['buffer_sample_bytes']==['81',None]
    assert r['terminal_byte']=='81'


def test_display_only_latency_is_73_tstates():
    data=[]
    for module in (v7,v8):
        image,symbols,_=module.build_image()
        _,_,events=_run(image,symbols,[1,0x8A])
        data.append([e for e in events if e[:2]==('out',3)])
    assert [b[3]-a[3] for a,b in zip(*data)][:10]==[0]*9+[73]


def test_release_reproduces_builder():
    image,symbols,_=v8.build_image()
    release=v8.v3.HERE/'releases/stock-context-v8/micron1_stock_context_v8.bin'
    assert release.read_bytes()==image
    manifest=json.loads(release.with_suffix('.json').read_text())
    assert manifest['checksums']['sha256']==hashlib.sha256(image).hexdigest()
    assert manifest['symbols']==symbols
    assert manifest['timing_vs_v7']['post_marker_snapshot_extra_tstates']==73
