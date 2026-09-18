import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
repo_root = Path(__file__).resolve().parents[2]
report_path = repo_root / "graphify-out" / "GRAPH_REPORT.md"
if not report_path.is_file():
    report_path = Path(__file__).resolve().with_name("GRAPH_REPORT.md")
report = report_path.read_text(encoding="utf-8")

# Extract sections
import re
sections = ["God Nodes", "Surprising Connections", "Suggested Questions"]
for section in sections:
    match = re.search(r"## " + section + r"(.*?)(?=\n## |\Z)", report, re.DOTALL)
    if match:
        print(f"## {section}{match.group(1)[:2000]}")
        print()
