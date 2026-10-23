"""Offline variable-run experiment. Decoder success is NOT Premiere compatibility."""
import struct
from .decode_graphic_text import decode_runs
from .native_styled_text_probe import replace_run_text


def rebuild_runs(payload,requests):
    """Each request selects a donor run index and replacement text.

    Clone donor payloads rather than guessing opaque style-table structure.
    Internal relative pointers remain intact. This intentionally trades size
    for structural preservation; it is not an optimized native serializer.
    """
    donors=decode_runs(payload)
    if not 1<=len(requests)<=256:raise ValueError('Probe supports 1–256 runs')
    if len(payload)*(len(requests)+1)>64*1024*1024:raise ValueError('Probe size budget exceeded')
    if struct.unpack_from('<I',payload,0)[0]!=len(payload)-12:raise ValueError('Unsupported header')
    for index,text in requests:
        if type(index) is not int or not 0<=index<len(donors):raise ValueError('Invalid donor run')
        if not isinstance(text,str) or not text or '\x00' in text:raise ValueError('Invalid text')
    def ptr(offset):return offset+struct.unpack_from('<I',payload,offset)[0]
    def field(table,index):
        vt=table-struct.unpack_from('<i',payload,table)[0]
        return table+struct.unpack_from('<H',payload,vt+4+index*2)[0]
    document=ptr(field(ptr(12),0));vector_field=field(document,0)
    output=bytearray(payload);output.extend(b'\x00'*((-len(output))%4));vector=len(output)
    output.extend(struct.pack('<I',len(requests))+b'\x00'*(4*len(requests)))
    for i,(donor,text) in enumerate(requests):
        fragments=[r['text'] for r in donors];fragments[donor]=text
        clone=replace_run_text(payload,fragments)
        output.extend(b'\x00'*((-len(output))%4));base=len(output);output.extend(clone)
        entry=vector+4+i*4;target=base+donors[donor]['table_offset']
        struct.pack_into('<I',output,entry,target-entry)
    struct.pack_into('<I',output,vector_field,vector-vector_field)
    struct.pack_into('<I',output,0,len(output)-12)
    decoded=decode_runs(bytes(output))
    for actual,(donor,text) in zip(decoded,requests):
        if actual['text']!=text:raise ValueError('Text mismatch')
        for key in ('font_index','font_postscript','font_size_raw','fill_rgb_explicit'):
            if actual[key]!=donors[donor][key]:raise ValueError('Donor style mismatch')
    return bytes(output)
