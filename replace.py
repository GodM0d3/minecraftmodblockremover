"""
Ersetzt Blöcke in einer Minecraft-Welt anhand der blocks.json Konfiguration.
"""

from pathlib import Path
from collections import Counter

try:
    import amulet
    from amulet.api.block import Block
    from amulet.api.errors import ChunkLoadError, ChunkDoesNotExist
except ImportError:
    print("Bitte zuerst amulet-core installieren: pip install amulet-core")
    raise

from config import load_config, show_config
from analyze import analyze_world, print_analysis


def replace_blocks(level, dimension: str, game_version: tuple,
                   old_block_id: str, new_block_id: str) -> int:
    """
    Ersetzt alle Vorkommen von old_block_id durch new_block_id.
    Gibt die Anzahl der ersetzten Blöcke zurück.
    """
    import numpy as np

    namespace, name = new_block_id.split(":", 1)
    new_block_versioned = Block(namespace, name)
    new_block_universal, _, _ = level.translation_manager.get_version(
        *game_version
    ).block.to_universal(new_block_versioned)

    all_chunks = list(level.all_chunk_coords(dimension))
    total = len(all_chunks)
    replaced_total = 0

    print(f"\n  Ersetze '{old_block_id}' -> '{new_block_id}'")
    print(f"  Verarbeite {total:,} Chunks...\n")

    for i, (cx, cz) in enumerate(all_chunks, 1):
        if i % 50 == 0 or i == total:
            pct = i / total * 100
            bar = "=" * int(pct / 5) + "-" * (20 - int(pct / 5))
            print(f"  [{bar}] {pct:5.1f}%  ersetzt: {replaced_total:,}", end="\r", flush=True)

        try:
            chunk = level.get_chunk(cx, cz, dimension)
        except (ChunkLoadError, ChunkDoesNotExist):
            continue
        except Exception:
            continue

        try:
            blocks_array = chunk.blocks
            palette = chunk.block_palette

            old_indices = []
            for idx in range(len(palette)):
                try:
                    universal_block = palette[idx]
                    versioned_block, _ = level.translation_manager.get_version(
                        *game_version
                    ).block.from_universal(universal_block)
                    if isinstance(versioned_block, Block):
                        if versioned_block.namespaced_name == old_block_id:
                            old_indices.append(idx)
                except Exception:
                    pass

            if not old_indices:
                continue

            new_idx = chunk.block_palette.get_add_block(new_block_universal)
            chunk_replaced = 0

            for old_idx in old_indices:
                mask = blocks_array == old_idx
                count = int(__import__("numpy").sum(mask))
                if count > 0:
                    blocks_array[mask] = new_idx
                    chunk_replaced += count

            if chunk_replaced > 0:
                chunk.changed = True
                replaced_total += chunk_replaced

        except Exception:
            pass

    print(" " * 70, end="\r")
    return replaced_total


def run_replace(world_path: str, dimension: str, game_version: tuple) -> None:
    """Lädt die Welt, analysiert sie und führt alle Ersetzungen aus der config durch."""
    replacements = load_config()

    if not replacements:
        print("\n  Keine Ersetzungen konfiguriert. Bitte zuerst 'config' aufrufen.\n")
        return

    path = Path(world_path).expanduser().resolve()
    if not path.exists():
        print(f"  Fehler: Pfad nicht gefunden: {path}")
        return

    print(f"\n  Lade Welt...")
    try:
        level = amulet.load_level(str(path))
    except Exception as e:
        print(f"  Fehler: Konnte Welt nicht laden: {e}")
        return

    try:
        # Schritt 1: Erst analysieren damit wir wissen was vorhanden ist
        print("\n  Analysiere Welt vor dem Ersetzen...")
        block_counts = analyze_world(level, dimension, game_version)
        print_analysis(block_counts)

        # Schritt 2: Prüfen welche Blöcke aus der Config tatsächlich vorkommen
        print("\n  Geplante Ersetzungen:")
        show_config(replacements)

        active = []
        skipped = []
        for entry in replacements:
            if entry["from"] in block_counts:
                count = block_counts[entry["from"]]
                active.append((entry["from"], entry["to"], count))
            else:
                skipped.append(entry["from"])

        if skipped:
            print(f"  Hinweis: Diese Blöcke wurden nicht gefunden und werden übersprungen:")
            for s in skipped:
                print(f"    - {s}")

        if not active:
            print("\n  Keine der konfigurierten Blöcke wurden in der Welt gefunden.\n")
            return

        print(f"\n  Folgende Ersetzungen werden durchgeführt:")
        for old, new, count in active:
            print(f"    {count:>10,}x  '{old}' -> '{new}'")

        print(f"\n  ACHTUNG: Dies ändert die Welt-Dateien dauerhaft!")
        print(f"  Minecraft sollte während der Bearbeitung geschlossen sein.\n")
        confirm = input("  Fortfahren? [j/N]: ").strip().lower()

        if confirm not in ("j", "ja", "y", "yes"):
            print("  Abgebrochen.")
            return

        # Schritt 3: Ersetzen
        total_replaced = 0
        for old_block, new_block, _ in active:
            replaced = replace_blocks(level, dimension, game_version, old_block, new_block)
            total_replaced += replaced
            print(f"  ✓ {replaced:,}x '{old_block}' -> '{new_block}'")

        print(f"\n  Speichere Änderungen...")
        level.save()
        print(f"  Fertig! {total_replaced:,} Blöcke insgesamt ersetzt und gespeichert.\n")

    finally:
        level.close()