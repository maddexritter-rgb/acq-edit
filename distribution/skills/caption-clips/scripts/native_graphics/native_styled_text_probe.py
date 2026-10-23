"""Experimental text-only mutation retaining an existing native style graph.

Not production: Premiere must reopen and render a project containing the result.
Only the observed format and the existing styled-run topology are supported.
"""
import struct
from .decode_graphic_text import decode_runs


def replace_font_identifiers(payload, replacements):
    """Diagnostic only: test alternate identifiers, not font-family substitution."""
    decode_runs(payload)
    if struct.unpack_from('<I',payload,0)[0]!=len(payload)-12:
        raise ValueError('Unsupported payload length header')
    def ptr(o):return o+struct.unpack_from('<I',payload,o)[0]
    def field(t,i):
        vt=t-struct.unpack_from('<i',payload,t)[0]
        return t+struct.unpack_from('<H',payload,vt+4+2*i)[0]
    document=ptr(field(ptr(12),0));vector=ptr(field(document,1))
    count=struct.unpack_from('<I',payload,vector)[0]
    result=bytearray(payload);found=set()
    for i in range(count):
        o=vector+4+4*i;s=ptr(o);n=struct.unpack_from('<I',payload,s)[0]
        name=payload[s+4:s+4+n].decode('utf-8')
        if name not in replacements:continue
        replacement=replacements[name]
        if not isinstance(replacement,str) or not replacement or '\x00' in replacement:
            raise ValueError('Invalid font identifier')
        result.extend(b'\x00'*((-len(result))%4));target=len(result)
        text=replacement.encode('utf-8')
        result.extend(struct.pack('<I',len(text))+text+b'\x00')
        struct.pack_into('<I',result,o,target-o);found.add(name)
    if found!=set(replacements):raise ValueError('Requested font not present')
    result.extend(b'\x00'*((-len(result))%4))
    struct.pack_into('<I',result,0,len(result)-12)
    decode_runs(bytes(result))
    return bytes(result)


def replace_run_text(payload, fragments):
    runs=decode_runs(payload)
    if len(runs)!=len(fragments):
        raise ValueError('Existing styled-run topology must be preserved')
    if struct.unpack_from('<I',payload,0)[0]!=len(payload)-12:
        raise ValueError('Unsupported payload length header')
    if not all(isinstance(x,str) and x and '\x00' not in x for x in fragments):
        raise ValueError('Nonempty NUL-free text required')
    output=bytearray(payload)
    for run,text in zip(runs,fragments):
        table=run['table_offset']
        vtable=table-struct.unpack_from('<i',payload,table)[0]
        field=table+struct.unpack_from('<H',payload,vtable+4)[0]
        output.extend(b'\x00'*((-len(output))%4))
        destination=len(output)
        encoded=text.encode('utf-8')
        output.extend(struct.pack('<I',len(encoded))+encoded+b'\x00')
        struct.pack_into('<I',output,field,destination-field)
    output.extend(b'\x00'*((-len(output))%4))
    struct.pack_into('<I',output,0,len(output)-12)
    decoded=decode_runs(bytes(output))
    if [r['text'] for r in decoded]!=fragments:raise ValueError('Roundtrip mismatch')
    for before,after in zip(runs,decoded):
        for key in ('style_table_offset','font_postscript','font_size_raw','fill_rgb_explicit'):
            if before[key]!=after[key]:raise ValueError('Style changed')
    return bytes(output)
