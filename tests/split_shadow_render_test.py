import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'python'), str(ROOT / 'distribution/skills/horizontal-to-vertical/scripts')]
from common import sha
from split_shadow_render import verify


class ExportLineageTests(unittest.TestCase):
    def test_receipt_and_native_substitution_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            parent, native, receipt = [root / n for n in ('parent.json', 'native.json', 'receipt.json')]
            parent.write_text('{}'); native.write_text('{}')
            receipt.write_text(json.dumps({'parent': str(parent), 'parentSha256': sha(parent),
                'nativeProject': str(native), 'nativeSha256': sha(native)}))
            packet = {'shadowReceipt': str(receipt), 'shadowReceiptSha256': sha(receipt)}
            native.write_text('{"changed":true}')
            with self.assertRaisesRegex(RuntimeError, 'lineage changed'):
                verify({'root': folder}, packet, native, {}, 1)
            with self.assertRaisesRegex(RuntimeError, 'another native'):
                verify({'root': folder}, packet, parent, {}, 1)
            receipt.write_text('{}')
            with self.assertRaisesRegex(RuntimeError, 'receipt changed'):
                verify({'root': folder}, packet, native, {}, 1)


if __name__ == '__main__': unittest.main()
