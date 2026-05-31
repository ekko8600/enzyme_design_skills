"""No-pytest smoke test for enzyme-design core workflows."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from enzyme_design.config import Settings
from enzyme_design.diagnostics.doctor import doctor
from enzyme_design.skill_api import EnzymeDesignSkillAPI


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        settings = Settings.from_env(root)
        api = EnzymeDesignSkillAPI(settings)
        note = root / "smoke-paper.md"
        note.write_text(
            "# Smoke Paper\n\n## Result\n\nThis smoke test discusses zinc binding evidence.",
            encoding="utf-8",
        )

        print("[1/6] ingest")
        document_id = api.ingest(note)
        assert document_id

        print("[2/6] analyze dry-run")
        analysis_path = api.analyze(document_id, dry_run=True)
        assert analysis_path.exists()

        print("[3/6] build wiki")
        wiki_paths = api.build_wiki()
        assert any(path.name == "index.md" for path in wiki_paths)

        print("[4/6] rebuild search index")
        count = api.rebuild_search_index(full=True)
        assert count > 0

        print("[5/6] ask dry-run")
        answer = api.ask("What discusses zinc binding evidence?", dry_run=True)
        assert "Evidence Matrix" in answer
        assert "zinc binding evidence" in answer

        print("[6/6] doctor")
        report = doctor(settings)
        assert "summary" in report
        assert int(report["summary"]["fail"]) == 0

    print("smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
