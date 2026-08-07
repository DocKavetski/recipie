from pathlib import Path
import re, json
from collections import Counter

text = Path(r"D:\Проекты\Рецепты\data\protocols_extract.txt").read_text(encoding="utf-8")

# words before мг / мг/сут / табл
near = re.findall(r"([А-ЯЁа-яёA-Za-z][А-ЯЁа-яёA-Za-z\-]{3,})\s+(?:\d+[\.,]?\d*\s*)?(?:-|–)?\s*\d*[\.,]?\d*\s*мг", text, flags=re.I)
c = Counter(w for w in near)
Path(r"D:\Проекты\Рецепты\data\near_mg.json").write_text(
    json.dumps(c.most_common(200), ensure_ascii=False, indent=2), encoding="utf-8"
)
print("near_mg unique", len(c))

# Lines containing 'табл' or 'капс'
lines = []
for line in text.splitlines():
    low = line.lower()
    if any(x in low for x in ("табл", "капс", "р-р", "раствор", "мг/", " мг ")):
        if re.search(r"[А-ЯЁа-яё]{4,}", line):
            lines.append(line.strip())
Path(r"D:\Проекты\Рецепты\data\drugish_lines.txt").write_text("\n".join(lines[:500]), encoding="utf-8")
print("lines", len(lines))
