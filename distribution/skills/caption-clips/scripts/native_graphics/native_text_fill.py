"""Change only explicit RGB bytes in an observed native Source Text payload.

Absent/default channels are refused. This establishes serialized intent only;
Premiere save/reopen and rendered color remain separate checks.
"""
import struct
from .decode_graphic_text import decode_runs


def recolor_runs(payload, rgb):
    if len(rgb) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in rgb):
        raise ValueError('Three byte RGB channels required')
    before = decode_runs(payload)
    result = bytearray(payload)
    changed = set()

    def field(table, index):
        vt = table - struct.unpack_from('<i', result, table)[0]
        if vt < 0 or vt + 4 > len(result):
            raise ValueError('Invalid native style vtable')
        size = struct.unpack_from('<H', result, vt)[0]
        slot = 4 + index * 2
        if size < slot + 2 or vt + size > len(result):
            raise ValueError('Explicit native color field required')
        offset = struct.unpack_from('<H', result, vt + slot)[0]
        if not offset or not 0 <= table + offset < len(result):
            raise ValueError('Explicit native color value required')
        return table + offset

    for run in before:
        if run['fill_rgb_explicit'] is None:
            raise ValueError('Partial/default fill cannot be recolored')
        pointer = field(run['style_table_offset'], 2)
        color = pointer + struct.unpack_from('<I', result, pointer)[0]
        for channel, value in enumerate(rgb):
            at = field(color, channel)
            result[at] = value
            changed.add(at)
    after = decode_runs(result)
    for old, new in zip(before, after):
        for key in old:
            if key not in ('fill_rgb_explicit', 'fill_hex_explicit') and old[key] != new[key]:
                raise ValueError('Recolor changed another text property')
        if new['fill_rgb_explicit'] != list(rgb):
            raise ValueError('Native color readback mismatch')
    if len(result) != len(payload) or any(a != b and i not in changed for i, (a,b) in enumerate(zip(payload,result))):
        raise ValueError('Unexpected payload mutation')
    return bytes(result)


def disable_document_shadow(payload):
    """Opt-in observed document-field-11 transport; native A/B required.

    Only the active document's explicit boolean is changed. Typography and
    unrelated document fields remain byte-identical. Unknown layouts fail.
    """
    before=decode_runs(payload);data=bytearray(payload)
    def field(table,index):
        vt=table-struct.unpack_from('<i',data,table)[0]
        size=struct.unpack_from('<H',data,vt)[0]
        if size<6+index*2:raise ValueError('Document field absent')
        offset=struct.unpack_from('<H',data,vt+4+index*2)[0]
        if not offset:raise ValueError('Document field not explicit')
        return table+offset
    root=12+struct.unpack_from('<I',data,12)[0]
    at=field(root,0);document=at+struct.unpack_from('<I',data,at)[0]
    flag=field(document,11)
    if data[flag] not in (0,1):raise ValueError('Unknown document effect flag')
    # Observed adjacent native shadow opacity, size, distance, blur and angle.
    values=[struct.unpack_from('<f',data,field(document,i))[0] for i in range(12,17)]
    if not (0<=values[0]<=100 and all(0<=v<=1000 for v in values[1:4]) and -360<=values[4]<=360):raise ValueError('Unknown shadow record')
    data[flag]=0
    if decode_runs(data)!=before:raise ValueError('Shadow transport changed text properties')
    if any(a!=b and i!=flag for i,(a,b) in enumerate(zip(payload,data))):raise ValueError('Unexpected shadow payload change')
    return bytes(data)
