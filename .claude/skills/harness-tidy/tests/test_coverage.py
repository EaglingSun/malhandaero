"""inventory.py --coverage 의 새 ID · 변경 유형 검사 (HT-07 · HT-18).

실행: python -m unittest discover -s tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import inventory  # noqa: E402

HEADER = (
    "| 행 | 새 ID | 변경 유형 | 정리본 (한 줄) | 원본 줄 | 원본 인용 | 비고 (묶은 ID · 이동한 곳 · 뺀 사유) | Eval 케이스 |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def row(m, rid, kind, case="1"):
    return f"| {m} | {rid} | {kind} | 정리본 | 10 | 「원문」 | | {case} |\n"


class CoverageIdTest(unittest.TestCase):
    def make(self, rows):
        d = Path(tempfile.mkdtemp())
        (d / "mapping.md").write_text("# 매핑표\n\n" + HEADER + "".join(rows) + "\n## 다른 표\n| a |\n|---|\n| — |\n", encoding="utf-8")
        (d / "evals.json").write_text(json.dumps({"evals": [{"id": 1, "expected_output": "[AB-01][M01]"}]}), encoding="utf-8")
        return d

    def test_moved_row_without_id_is_flagged(self):
        d = self.make([row("M01", "AB-01", "유지"), row("M02", "—", "이동")])
        c = inventory.coverage(d)
        self.assertEqual(c["no_id"], ["M02 (이동)"])
        self.assertFalse(inventory.coverage_ok(c))

    def test_empty_id_is_flagged(self):
        c = inventory.coverage(self.make([row("M01", "", "수정")]))
        self.assertEqual(c["no_id"], ["M01 (수정)"])

    def test_removed_row_without_id_or_reason_is_flagged(self):
        c = inventory.coverage(self.make([row("M01", "-", "뺄", "없음(사유: 중복)")]))
        self.assertEqual(c["no_id"], ["M01 (뺄)"])

    def test_reason_instead_of_id_is_accepted(self):
        c = inventory.coverage(self.make([row("M01", "AB-01", "유지"), row("M02", "없음(사유: 제목)", "유지", "없음(사유: 제목)")]))
        self.assertEqual(c["no_id"], [])
        self.assertTrue(inventory.coverage_ok(c))

    def test_unknown_change_kind_is_flagged(self):
        c = inventory.coverage(self.make([row("M01", "AB-01", "위치")]))
        self.assertEqual(c["bad_kind"], ["M01 (위치)"])
        self.assertFalse(inventory.coverage_ok(c))

    def test_rc1_table_without_row_column(self):
        d = Path(tempfile.mkdtemp())
        (d / "mapping.md").write_text(
            "| 새 ID | 변경 유형 | 정리본 (한 줄) | 원본 줄 | 원본 인용 | 비고 |\n|---|---|---|---|---|---|\n"
            "| AB-01 | 유지 | x | 1 | 「x」 | |\n| — | 이동 | x | 2 | 「y」 | |\n", encoding="utf-8")
        (d / "evals.json").write_text(json.dumps({"evals": [{"id": 1, "expected_output": "[AB-01]"}]}), encoding="utf-8")
        c = inventory.coverage(d)
        self.assertEqual(c["no_id"], ["— (이동)"])

    def test_cli_exit_code_fails_on_missing_id(self):
        d = self.make([row("M01", "—", "이동")])
        p = subprocess.run([sys.executable, str(SCRIPTS / "inventory.py"), "--coverage", str(d)],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 1)
        self.assertIn("ID 없음", p.stdout)


if __name__ == "__main__":
    unittest.main()
