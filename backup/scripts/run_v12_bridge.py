from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "v12_port"))

from questions import QUESTIONS  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ported paper_visual_rag v12 bridge pipeline from this benchmark workspace.")
    parser.add_argument("--bridge", default="대안천교")
    parser.add_argument("--question-ids", nargs="*", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Only show selected questions and paths; do not call models.")
    args = parser.parse_args()

    selected = [q for q in QUESTIONS if args.question_ids is None or q["id"] in args.question_ids]
    if args.dry_run:
        import config
        payload = {
            "bridge": args.bridge,
            "questions": selected,
            "pdf_path": config.BRIDGES[args.bridge]["pdf_path"],
            "results_dir": config.RESULTS_DIR,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    from scripts.run_full_v12_test import run_rag_v12_full_pipeline

    payload = run_rag_v12_full_pipeline(args.bridge, question_ids=args.question_ids)
    print(json.dumps({"bridge": args.bridge, "total_questions": payload.get("total_questions")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
