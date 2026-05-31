import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
report = Path("graphify-out/GRAPH_REPORT.md").read_text(encoding="utf-8")

# Extract sections
import re
sections = ["God Nodes", "Surprising Connections", "Suggested Questions"]
for section in sections:
    match = re.search(r"## " + section + r"(.*?)(?=\n## |\Z)", report, re.DOTALL)
    if match:
        print(f"## {section}{match.group(1)[:2000]}")
        print()
