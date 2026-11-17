"""
Run the RAG benchmark (evaluation/eval_dataset.json) from the command line.

  python evaluation/run_benchmark.py          # 5 systems + 6 ablations (offline, reproducible)
  python evaluation/run_benchmark.py --llm    # full system: extractive vs the configured LLM

Results are written to evaluation/results/ (latest.* and llm_comparison.*);
the web dashboard's Evaluation page shows the main report.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Config  # noqa: E402
from backend.evaluation import run_benchmark, run_llm_comparison, to_markdown  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="compare extractive vs LLM answer generation")
    args = parser.parse_args()
    last = {"msg": ""}

    def progress(fraction: float, message: str) -> None:
        if message != last["msg"]:
            print(f"[{fraction * 100:5.1f}%] {message}", flush=True)
            last["msg"] = message

    if args.llm:
        run_llm_comparison(progress=progress)
        print((Config.EVAL_RESULTS_DIR / "llm_comparison.md").read_text(encoding="utf-8"))
    else:
        print(to_markdown(run_benchmark(progress=progress)))


if __name__ == "__main__":
    main()
