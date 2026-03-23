"""
Analyse einer Minecraft-Welt.
Delegiert immer an manager.run_analyze_parallel().
"""

from collections import Counter
from pathlib import Path
import json
import datetime

from manager import run_analyze_parallel


# ─────────────────────────────────────────────
#  Ausgabe
# ─────────────────────────────────────────────

def print_analysis(block_counts: Counter, top_n=None) -> None:
    """Gibt die sortierten Ergebnisse in der Konsole aus."""
    if not block_counts:
        print("  Keine Blöcke gefunden.\n")
        return

    total_blocks = sum(block_counts.values())
    shown = block_counts.most_common(top_n) if top_n else block_counts.most_common()

    print(f"\n  Analyse abgeschlossen!\n")
    print(f"  {'='*62}")
    print(f"  Gesamt Blöcke:  {total_blocks:>15,}")
    print(f"  Unique Typen:   {len(block_counts):>15,}")
    if top_n:
        print(f"  (Zeige Top {top_n})")
    print(f"  {'='*62}")
    print(f"  {'Block-ID':<42} {'Anzahl':>10}  {'%':>5}")
    print(f"  {'-'*42} {'-'*10}  {'-'*5}")

    for block_id, count in shown:
        pct = count / total_blocks * 100
        bar = "#" * min(15, max(1, int(pct / 2)))
        print(f"  {block_id:<42} {count:>10,}  {pct:>4.1f}%  {bar}")

    print(f"  {'='*62}\n")


# ─────────────────────────────────────────────
#  JSON-Export
# ─────────────────────────────────────────────

def save_analysis_json(block_counts: Counter, world_path: str,
                       dimension: str) -> Path:
    """Speichert die Analyse als JSON-Datei."""
    world_name = Path(world_path).name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(f"analysis_{world_name}_{timestamp}.json")

    total_blocks = sum(block_counts.values())
    data = {
        "meta": {
            "world": world_name,
            "world_path": str(world_path),
            "dimension": dimension,
            "analyzed_at": datetime.datetime.now().isoformat(),
            "total_blocks": total_blocks,
            "unique_block_types": len(block_counts),
        },
        "blocks": [
            {
                "id": block_id,
                "count": count,
                "percent": round(count / total_blocks * 100, 4),
            }
            for block_id, count in block_counts.most_common()
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path


# ─────────────────────────────────────────────
#  Einstiegspunkt
# ─────────────────────────────────────────────

def run_analyze(world_path: str, dimension: str,
                top_n=None, num_workers: int = 4) -> Counter:
    """Analysiert die Welt parallel und speichert das Ergebnis als JSON."""
    path = Path(world_path).expanduser().resolve()
    if not path.exists():
        print(f"  Fehler: Pfad nicht gefunden: {path}")
        return Counter()

    block_counts = run_analyze_parallel(str(path), dimension, num_workers)

    print_analysis(block_counts, top_n=top_n)

    if block_counts:
        try:
            json_path = save_analysis_json(block_counts, str(path), dimension)
            print(f"  Analyse gespeichert: {json_path}\n")
        except Exception as e:
            print(f"  Warnung: JSON konnte nicht gespeichert werden: {e}\n")

    return block_counts