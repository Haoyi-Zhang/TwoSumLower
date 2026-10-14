"""Regression guards for two source-edition-sensitive bibliography records.

Mutations are in memory. Matching ledger mutations bypass generic snapshot/ledger
agreement, so each case reaches the record-specific guard in standalone replay.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import bibliography_audit as bibliography  # noqa: E402


class BibliographyHighRiskRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entries, cls.cited_keys = bibliography.load_snapshot()
        cls.ledger = bibliography.load_ledger()
        cls.baseline = bibliography.audit()

    def assert_record_rejected(self, key: str, field: str, bad_value: str,
                               expected_error: str) -> None:
        self.assertTrue(self.baseline["passed"])
        entries = copy.deepcopy(self.entries)
        ledger = copy.deepcopy(self.ledger)
        entries[key][field] = bad_value
        ledger[key][field] = bad_value

        # Model an extracted standalone artifact without altering any source file.
        absent_paper = ROOT / "__absent_paper_for_bibliography_test__"
        self.assertFalse(absent_paper.exists())
        with mock.patch.object(bibliography, "load_snapshot",
                               return_value=(entries, self.cited_keys)), \
             mock.patch.object(bibliography, "load_ledger", return_value=ledger), \
             mock.patch.object(bibliography, "BIB_PATH", absent_paper / "references.bib"), \
             mock.patch.object(bibliography, "TEX_PATH", absent_paper / "main.tex"):
            with self.assertRaisesRegex(bibliography.AuditError, expected_error):
                bibliography.audit()

    def test_kahan_notes_reject_1996_date(self) -> None:
        self.assert_record_rejected(
            "IEEEExceptions", "year", "1996",
            "Kahan 1997 author-dated lecture-note record regressed",
        )

    def test_published_popl_title_rejects_preprint_on_prefix(self) -> None:
        self.assert_record_rejected(
            "SoundCompilationReals", "title", "On Sound Compilation of Reals",
            "published POPL 2014 Darulova-Kuncak title/DOI regressed",
        )


if __name__ == "__main__":
    unittest.main()
