"""
Ersetzt Blöcke in einer Minecraft-Welt anhand der blocks.json Konfiguration.
Delegiert immer an manager.run_replace_parallel().
"""

from pathlib import Path

from config import load_config, show_config
from analyze import run_analyze, print_analysis
from manager import run_replace_parallel


def run_replace(world_path: str, dimension: str, num_workers: int = 4) -> None:
    """
    Analysiert die Welt, zeigt die geplanten Ersetzungen und führt sie parallel durch.
    """
    replacements = load_config()

    if not replacements:
        print("\n  Keine Ersetzungen konfiguriert. Bitte zuerst 'config' aufrufen.\n")
        return

    path = Path(world_path).expanduser().resolve()
    if not path.exists():
        print(f"  Fehler: Pfad nicht gefunden: {path}")
        return

    # Analyse vorab, damit wir wissen welche Blöcke überhaupt vorkommen
    print("\n  Analysiere Welt vor dem Ersetzen...")
    block_counts = run_analyze(str(path), dimension, num_workers=num_workers)

    # Planen
    print("\n  Geplante Ersetzungen:")
    show_config(replacements)

    active = []
    skipped = []
    for entry in replacements:
        if entry["from"] in block_counts:
            active.append((entry["from"], entry["to"], block_counts[entry["from"]]))
        else:
            skipped.append(entry["from"])

    if skipped:
        print("  Hinweis: Diese Blöcke wurden nicht gefunden und werden übersprungen:")
        for s in skipped:
            print(f"    - {s}")

    if not active:
        print("\n  Keine der konfigurierten Blöcke wurden in der Welt gefunden.\n")
        return

    print("\n  Folgende Ersetzungen werden durchgeführt:")
    for old, new, count in active:
        print(f"    {count:>10,}x  '{old}' -> '{new}'")

    print(f"\n  ACHTUNG: Dies ändert die Welt-Dateien dauerhaft!")
    print(f"  Minecraft sollte während der Bearbeitung geschlossen sein.\n")
    confirm = input("  Fortfahren? [j/N]: ").strip().lower()
    if confirm not in ("j", "ja", "y", "yes"):
        print("  Abgebrochen.")
        return

    active_entries = [{"from": old, "to": new} for old, new, _ in active]

    total_replaced = run_replace_parallel(str(path), dimension, active_entries, num_workers)
    print(f"\n  Fertig! {total_replaced:,} Blöcke insgesamt ersetzt und gespeichert.\n")