"""
Advanced evaluation: baselines (LLM only, standard LangChain RAG), 95% error bars, significance tests,
error analysis and the Hindi/Hinglish benchmark. See backend/advanced_eval.py for the method.

  python evaluation/run_advanced.py                 # run / resume, keeping 250 Groq requests for the website
  python evaluation/run_advanced.py --reserve 100   # allow the benchmark to use more of today's allowance
  python evaluation/run_advanced.py --reset         # forget finished stages and score again (cached LLM
                                                    # answers are kept, so this costs no Groq quota)

Every Groq answer is cached, so stopping and re-running never pays twice. When the daily allowance gets down
to the reserve the run stops by itself; run it again later (e.g. tomorrow) and it continues where it stopped.
Results: evaluation/results/advanced_eval.{json,md} and the Evaluation page of the web app.
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Config  # noqa: E402
from backend.advanced_eval import run_advanced, to_markdown  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reserve", type=int, default=250, help="Groq requests to leave for the website (default 250)")
    parser.add_argument("--reset", action="store_true", help="re-score every stage (cached LLM answers are reused)")
    args = parser.parse_args()
    stage_dir = Config.DATA_DIR / "eval_cache" / "advanced"
    if args.reset and stage_dir.exists():
        for f in stage_dir.glob("*.json"):
            f.unlink()
    last = {"msg": ""}

    def progress(fraction: float, message: str) -> None:
        if message != last["msg"]:
            print(f"[{fraction * 100:5.1f}%] {message}", flush=True)
            last["msg"] = message

    report = run_advanced(reserve=args.reserve, progress=progress)
    print()
    print(to_markdown(report))
    g = report["groq"]
    print(f"Groq: {g['calls_this_run']} new calls, {g['answers_from_cache']} answers from cache, "
          f"{g['remaining_requests_today']} requests left today.")
    if not report["status"]["complete"]:
        print("\nNOT FINISHED:", report["status"]["paused_reason"] or "", "\nPending:",
              ", ".join(report["status"]["pending_stages"]))
        sys.exit(3)


if __name__ == "__main__":
    main()
