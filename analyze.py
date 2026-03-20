"""
Analyse einer Minecraft-Welt mit amulet-core.
Zählt alle Blocktypen und gibt eine sortierte Liste aus.
"""

from collections import Counter
from pathlib import Path

try:
    import amulet
    from amulet.api.block import Block
    from amulet.api.errors import ChunkLoadError, ChunkDoesNotExist
except ImportError:
    print("Bitte zuerst amulet-core installieren: pip install amulet-core")
    raise


def analyze_world(level, dimension: str, game_version: tuple) -> Counter:
    """
    Iteriert über alle Chunks und zählt jeden Blocktyp.
    Gibt einen Counter zurück: { 'minecraft:stone': 12345, ... }
    """
    import numpy as np

    block_counts = Counter()
    all_chunks = list(level.all_chunk_coords(dimension))
    total = len(all_chunks)

    if total == 0:
        print(f"  Keine Chunks in Dimension '{dimension}' gefunden.")
        return block_counts

    print(f"\n  Welt:      {Path(level.level_path).name}")
    print(f"  Dimension: {dimension}")
    print(f"  Chunks:    {total:,}")
    print(f"\n  Analysiere...\n")

    for i, (cx, cz) in enumerate(all_chunks, 1):
        if i % 50 == 0 or i == total:
            pct = i / total * 100
            bar = "=" * int(pct / 5) + "-" * (20 - int(pct / 5))
            print(f"  [{bar}] {pct:5.1f}%  ({i:,}/{total:,})", end="\r", flush=True)

        try:
            chunk = level.get_chunk(cx, cz, dimension)
        except (ChunkLoadError, ChunkDoesNotExist):
            continue
        except Exception:
            continue

        try:
            blocks_array = chunk.blocks
            palette = chunk.block_palette
            unique_indices, counts = np.unique(blocks_array, return_counts=True)

            for idx, count in zip(unique_indices, counts):
                try:
                    universal_block = palette[idx]
                    versioned_block, _ = level.translation_manager.get_version(
                        *game_version
                    ).block.from_universal(universal_block)
                    if isinstance(versioned_block, Block):
                        block_counts[versioned_block.namespaced_name] += count
                except Exception:
                    pass
        except Exception:
            pass

    print(" " * 70, end="\r")
    return block_counts


def print_analysis(block_counts: Counter, top_n=None) -> None:
    """Gibt die sortierten Ergebnisse aus."""
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


def run_analyze(world_path: str, dimension: str, game_version: tuple, top_n=None) -> Counter:
    """Lädt die Welt, analysiert sie und gibt den Counter zurück."""
    path = Path(world_path).expanduser().resolve()
    if not path.exists():
        print(f"  Fehler: Pfad nicht gefunden: {path}")
        return Counter()

    print(f"\n  Lade Welt...")
    try:
        level = amulet.load_level(str(path))
    except Exception as e:
        print(f"  Fehler: Konnte Welt nicht laden: {e}")
        return Counter()

    try:
        block_counts = analyze_world(level, dimension, game_version)
        print_analysis(block_counts, top_n=top_n)
        return block_counts
    finally:
        level.close()