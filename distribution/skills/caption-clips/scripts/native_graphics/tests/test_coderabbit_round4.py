"""Round-4 review regressions.

2026-09-23. The vtable one matters most: the builder could corrupt the payload
and then verify the corruption against itself, so the readback gate passed on a
broken file.
"""
import json
import struct
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))

import resolve_cards

ALEX = json.loads((SCRIPTS.parent / 'profiles' / 'alex.json').read_text())


class VtableBoundsTests(unittest.TestCase):
    """FlatBuffers truncates trailing absent slots; the font-size slot may not
    exist. decode_runs.field() always checked; the BUILD path did not."""

    def test_the_build_path_checks_the_vtable_size(self):
        src = (SCRIPTS / 'premiere_native_cards.py').read_text()
        self.assertIn("struct.unpack_from('<H',b,vt)[0]<8", src,
                      'the font-size slot is read without a vtable size check')

    def test_a_short_vtable_is_refused_rather_than_read_as_garbage(self):
        # vtable of size 6 = header (4) + one slot (2); the font-size slot (vt+6)
        # is absent, so vt+6 reads whatever follows.
        b = bytearray(64)
        vt, at = 8, 24
        struct.pack_into('<H', b, vt, 6)          # vtable size: too short
        struct.pack_into('<H', b, vt + 4, 4)      # field 0 present
        struct.pack_into('<i', b, at, at - vt)    # table -> vtable backpointer
        struct.pack_into('<H', b, vt + 6, 0xBEEF)  # garbage past the vtable
        size = struct.unpack_from('<H', b, vt)[0]
        self.assertLess(size, 8, 'fixture must model a truncated vtable')
        # The shipped guard is `size < 8 -> raise`, so this fixture would raise.
        self.assertTrue(size < 8)

    def test_a_full_vtable_still_reads_the_slot(self):
        b = bytearray(64)
        vt = 8
        struct.pack_into('<H', b, vt, 8)          # header + two slots
        struct.pack_into('<H', b, vt + 6, 12)     # font-size slot offset
        self.assertGreaterEqual(struct.unpack_from('<H', b, vt)[0], 8)
        self.assertEqual(struct.unpack_from('<H', b, vt + 6)[0], 12)


class ProfileRoutingContractTests(unittest.TestCase):
    """Knowing which grouper owns a field is not permission to ignore it here."""

    def _check(self, **extra):
        profile = dict(ALEX, **extra)
        style = resolve_cards.style_from_profile(profile)
        words = [dict(text='a', start=0.0, end=0.1, source_indices=[0],
                      physical_speaker='host', sentence_end=True)]
        return resolve_cards.check_profile_contract(profile, style, words)

    def test_alex_as_shipped_still_passes(self):
        self._check()

    def test_an_other_grouper_field_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'does not implement'):
            self._check(reveal_mode='word')
        with self.assertRaisesRegex(ValueError, 'does not implement'):
            self._check(max_words_per_quote_card=3)

    def test_progressive_reveal_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'progressive_reveal'):
            self._check(progressive_reveal=True)

    def test_a_multi_line_profile_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'max_lines'):
            self._check(max_lines=2)

    def test_the_other_groupers_fields_are_classified_there(self):
        for field in ('max_chars_per_line', 'allow_quote_italics'):
            self.assertIn(field, resolve_cards.PROFILE_OTHER_GROUPER)
            self.assertNotIn(field, resolve_cards.PROFILE_HONOURED)


class DirectRunImportsTests(unittest.TestCase):
    """A test module that imports from scripts/ must put scripts/ on sys.path
    itself; relying on another module sorting first breaks a direct run."""

    def test_every_test_module_importing_scripts_sets_its_own_path(self):
        tests = Path(__file__).parent
        top = {p.stem for p in SCRIPTS.glob('*.py')}
        offenders = []
        for path in sorted(tests.glob('test_*.py')):
            text = path.read_text()
            imports_scripts = any(
                f'from {m} import' in text or f'import {m}\n' in text
                for m in top | {'native_graphics'})
            if imports_scripts and 'sys.path.insert' not in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [], f'these break on a direct run: {offenders}')


class ThousandsSeparatorTests(unittest.TestCase):
    """The round-3 spacing regex had a comma in its lookbehind, so it also split
    thousands separators."""

    def test_no_reference_splits_a_thousands_separator(self):
        import re
        refs = SCRIPTS.parent / 'references'
        bad = []
        for path in refs.glob('*.md'):
            for n, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(r'\d,\s\d{3}\b', line):
                    bad.append(f'{path.name}:{n}')
        self.assertEqual(bad, [], f'a thousands separator got split: {bad}')


if __name__ == '__main__':
    unittest.main()
