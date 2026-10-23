"""Read the observed Premiere Source Text FlatBuffer text-run vector.

This decodes structural run order, not rendered visibility or typography.
Unknown or malformed payloads raise rather than falling back to byte order.
"""
import struct


def interpret_synthetic_italic(raw):
    """Field15 calibrated by a byte-isolated native A/B, not font inference."""
    if raw is None:
        return None, 'ABSENT_DEFAULT_NOT_INFERRED'
    if raw in (0, 1):
        return bool(raw), 'FIELD15_NATIVE_AB_CALIBRATED_SINGLE_SCHEMA'
    return None, 'UNKNOWN_FIELD15_VALUE'


def decode_runs(data):
    def number(fmt, offset):
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(data):
            raise ValueError('Text payload offset outside buffer')
        return struct.unpack_from(fmt, data, offset)[0]

    def pointer(offset):
        target = offset + number('<I', offset)
        if target <= offset or target >= len(data):
            raise ValueError('Invalid forward pointer')
        return target

    def field(table, index, optional=False):
        vtable = table - number('<i', table)
        size = number('<H', vtable)
        entry = 4 + index * 2
        if size < entry + 2:
            if optional:
                return None
            raise ValueError('Required text table field absent')
        relative = number('<H', vtable + entry)
        if not relative:
            if optional:
                return None
            raise ValueError('Required text table field empty')
        return table + relative

    if data[8:12] != b'\x44\x33\x22\x11':
        raise ValueError('Unknown Source Text header')
    root = pointer(12)
    document = pointer(field(root, 0))
    fonts_vector = pointer(field(document, 1))
    fonts_count = number('<I', fonts_vector)
    if not 1 <= fonts_count <= 4096:
        raise ValueError('Invalid font count')
    fonts = []
    for i in range(fonts_count):
        at = pointer(fonts_vector + 4 + i * 4)
        length = number('<I', at)
        if at + 4 + length >= len(data) or data[at + 4 + length] != 0:
            raise ValueError('Invalid font string')
        fonts.append(data[at + 4:at + 4 + length].decode('utf-8'))
    vector = pointer(field(document, 0))
    count = number('<I', vector)
    if not 1 <= count <= 4096:
        raise ValueError('Invalid text run count')
    runs = []
    for index in range(count):
        table = pointer(vector + 4 + index * 4)
        string = pointer(field(table, 0))
        length = number('<I', string)
        start = string + 4
        if length > len(data) - start or start + length >= len(data):
            raise ValueError('Text string exceeds payload')
        if data[start + length] != 0:
            raise ValueError('Text string missing terminator')
        text = data[start:start + length].decode('utf-8')
        style = pointer(field(table, 1))
        font_field = field(style, 0, optional=True)
        font_index = number('<I', font_field) if font_field is not None else 0
        if font_index >= len(fonts):
            raise ValueError('Font index outside font vector')
        size_field = field(style, 1, optional=True)
        italic_field = field(style, 15, optional=True)
        italic_raw = number('<B', italic_field) if italic_field is not None else None
        italic, italic_status = interpret_synthetic_italic(italic_raw)
        fill_field = field(style, 2, optional=True)
        fill_rgb = None
        if fill_field is not None:
            color_table = pointer(fill_field)
            channels = [field(color_table, channel, optional=True) for channel in range(3)]
            # Preserve uncertainty instead of inventing defaults for omitted channels.
            if all(channel is not None for channel in channels):
                fill_rgb = [number('<B', channel) for channel in channels]
        runs.append({'index': index, 'text': text, 'table_offset': table,
                     'string_offset': string, 'style_table_offset': style,
                     'font_index': font_index, 'font_postscript': fonts[font_index],
                     'font_size_raw': number('<f', size_field) if size_field is not None else None,
                     'synthetic_italic_raw': italic_raw,
                     'synthetic_italic': italic,
                     'synthetic_italic_status': italic_status,
                     'fill_rgb_explicit': fill_rgb,
                     'fill_hex_explicit': '#'+''.join(f'{channel:02X}' for channel in fill_rgb) if fill_rgb is not None else None,
                     'fill_status': 'EXPLICIT_RGB_OBSERVED' if fill_rgb is not None else 'DEFAULT_OR_PARTIAL_COLOR_NOT_DECODED',
                     'style_status': 'OBSERVED_SCHEMA_REQUIRES_VISUAL_CALIBRATION'})
    return runs


# --- Paragraph (area) text box -------------------------------------------------
#
# A Graphic text layer is either POINT text (no box; Position is the text anchor)
# or PARAGRAPH text: the document table then carries the box size in ABSOLUTE
# pixels of the canvas it was authored on -- field 2 = width, field 3 = height.
# Only the layer Position is normalized. So a paragraph donor authored on a
# 2160x3840 template keeps a 2160-canvas box when cloned into 1080x1920: the text
# renders off-centre and the Program Monitor edit box does not fit the frame.
# Calibrated on native payloads (box 1770x1152 on a 2160x3840 template; point-text
# donors carry neither field). Every copy of the document table in a payload shares
# the root document's exact vtable layout, which is how the copies are found.

BOX_WIDTH_FIELD = 2
BOX_HEIGHT_FIELD = 3


def _document_layout(data):
    def number(fmt, offset):
        if offset < 0 or offset + struct.calcsize(fmt) > len(data):
            raise ValueError('Text payload offset outside buffer')
        return struct.unpack_from(fmt, data, offset)[0]
    if data[8:12] != b'\x44\x33\x22\x11':
        raise ValueError('Unknown Source Text header')
    root = 12 + number('<I', 12)
    root_vtable = root - number('<i', root)
    if number('<H', root_vtable) < 6 or not number('<H', root_vtable + 4):
        raise ValueError('Source Text root lacks a document')
    at = root + number('<H', root_vtable + 4)
    document = at + number('<I', at)
    vtable = document - number('<i', document)
    size = number('<H', vtable)
    if size < 4 or size % 2:
        raise ValueError('Invalid document vtable')
    return number, document, bytes(data[vtable:vtable + size])


def _box_slots(data, table, number):
    vtable = table - number('<i', table)
    size = number('<H', vtable)
    def slot(index):
        entry = 4 + index * 2
        if size < entry + 2:
            return None
        relative = number('<H', vtable + entry)
        return table + relative if relative else None
    return slot(BOX_WIDTH_FIELD), slot(BOX_HEIGHT_FIELD)


def text_boxes(data):
    """Every paragraph box in the payload: [{table, width_at, height_at, width, height}].

    The first entry is the root document's own box. An empty list means point text.
    A table is a document copy only if its vtable is byte-identical to the root
    document's, so arbitrary data is never reinterpreted as a box.
    """
    number, document, signature = _document_layout(data)
    boxes, seen = [], set()
    for table in [document] + list(range(4, len(data) - 4, 4)):
        if table in seen:
            continue
        try:
            vtable = table - number('<i', table)
        except ValueError:
            continue
        if not (0 <= vtable <= len(data) - len(signature)) or data[vtable:vtable + len(signature)] != signature:
            continue
        seen.add(table)
        width_at, height_at = _box_slots(data, table, number)
        if width_at is None and height_at is None:
            continue
        if width_at is None or height_at is None:
            raise ValueError('Paragraph box has only one dimension')
        boxes.append(dict(table=table, width_at=width_at, height_at=height_at,
                          width=number('<f', width_at), height=number('<f', height_at)))
    return boxes


def document_box(data):
    """(width, height) of the root document's paragraph box, or None for point text."""
    number, document, _ = _document_layout(data)
    width_at, height_at = _box_slots(data, document, number)
    if width_at is None and height_at is None:
        return None
    if width_at is None or height_at is None:
        raise ValueError('Paragraph box has only one dimension')
    return number('<f', width_at), number('<f', height_at)


def scale_text_boxes(data, scale_x, scale_y):
    """Return a copy with every paragraph box scaled; runs and all other fields untouched."""
    out = bytearray(data)
    boxes = text_boxes(bytes(data))
    for box in boxes:
        struct.pack_into('<f', out, box['width_at'], box['width'] * scale_x)
        struct.pack_into('<f', out, box['height_at'], box['height'] * scale_y)
    return out, len(boxes)
