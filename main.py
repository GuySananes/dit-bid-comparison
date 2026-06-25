# main.py
# Pipeline orchestrator — runs the full bid comparison pipeline.
#
# Usage:
#   python main.py --input data/raw/project_x/ --project "Project Name" --boq data/raw/boq.xlsx
#
# What this file does:
#   1. Parse all contractor Excel files (Layer 1)
#   2. Run normalization on all parsed data (Layer 2)
#   3. Run AI agents on flagged rows (Layer 3)
#   4. Build comparison table (script)
#   5. Generate contractor reference sheets (Agent C)
#   6. Generate executive summary (Agent D)
#   7. Write results to data/output/<project_id>/
#   8. Feed decisions back to Vector DB (learning loop)
#
# Each step is logged. If a step fails, the pipeline stops and reports which step.
# Intermediate JSON files are saved after each step so you can resume from any point.
#
# TODO: implement this file after all modules are built and tested individually.
# Suggested implementation order:
#   1. Wire Layer 1 only → verify JSON output
#   2. Add Layer 2 → verify normalization
#   3. Add Agent A → verify ambiguity resolution
#   4. Add Agent B → verify deviation flagging
#   5. Add comparison table script
#   6. Add Agent C + D
#   7. Add Vector DB learning loop

import argparse

def main():
    parser = argparse.ArgumentParser(description="DIT Bid Comparison Pipeline")
    parser.add_argument("--input",   required=True, help="Folder with contractor Excel files")
    parser.add_argument("--boq",     required=True, help="Path to BOQ Excel file")
    parser.add_argument("--project", required=True, help="Project name / ID")
    args = parser.parse_args()

    print(f"[Pipeline] Starting project: {args.project}")
    print(f"[Pipeline] Input folder: {args.input}")
    print(f"[Pipeline] BOQ file: {args.boq}")
    print("[Pipeline] TODO: implement pipeline steps")

if __name__ == "__main__":
    main()
