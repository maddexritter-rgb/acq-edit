"""Verify the framing owner's append-only shadow checkpoint before native export."""
from pathlib import Path
from common import inside, read, require, sha


def verify(project, packet, native, spec, frame_ticks):
    from composition_revision import without_shadow, verify_owned
    from framing_plan import verify_filmcraft_framing_data
    receipt_path = inside(project['root'], packet['shadowReceipt'])
    require(sha(receipt_path) == packet['shadowReceiptSha256'], 'Shadow receipt changed')
    receipt = read(receipt_path)
    parent = inside(project['root'], receipt['parent'])
    owned = inside(project['root'], receipt['nativeProject'])
    require(owned == Path(native).resolve(), 'Shadow receipt targets another native project')
    require(sha(parent) == receipt['parentSha256'] and sha(owned) == receipt['nativeSha256'], 'Shadow lineage changed')
    before, after = read(parent), read(owned)
    verify_owned(before, after, receipt['layoutIds'], receipt['profile'])
    verify_filmcraft_framing_data(without_shadow(after, receipt), spec, frame_ticks)
    return {'owner': 'horizontal-to-vertical', 'receipt': str(receipt_path),
            'receiptSha256': sha(receipt_path), 'nativeSha256': receipt['nativeSha256'],
            'parentSha256': receipt['parentSha256'], 'humanApproved': False}
