"""
Manager-Modul für den Minecraft Block Replacer.

Aufgaben des Managers:
  1. Welt öffnen und alle Chunk-Koordinaten laden
  2. Chunks nach Region gruppieren (je eine .mca-Datei = eine Arbeitseinheit)
  3. Regionen als Tasks an Worker-Pool verteilen
  4. Fortschritt in Echtzeit anzeigen
  5. Ergebnisse sammeln und zusammenführen
  6. Bei "replace": Chunks in die Welt zurückschreiben und speichern

Die Worker öffnen die Welt jeweils selbst (read-only) – keine geteilten
amulet-Objekte über Prozessgrenzen.
"""

from collections import Counter, defaultdict
from pathlib import Path
import multiprocessing as mp
import sys

import amulet
from amulet.api.block import Block
from amulet.api.errors import ChunkLoadError, ChunkDoesNotExist

from worker import worker_init, run_task


# ─────────────────────────────────────────────
#  Hilfsfunktionen
# ─────────────────────────────────────────────

def _group_chunks_by_region(chunk_coords: list) -> dict:
    """
    Gruppiert Chunk-Koordinaten nach ihrer Region-Datei.
    Region = (cx >> 5, cz >> 5), entspricht je einer .mca-Datei.
    Gibt ein Dict { (rx, rz): [(cx, cz), ...] } zurück.
    """
    regions: dict = defaultdict(list)
    for cx, cz in chunk_coords:
        regions[(cx >> 5, cz >> 5)].append((cx, cz))
    return dict(regions)


def _progress_bar(done: int, total: int, width: int = 20) -> str:
    pct = done / total * 100 if total else 0
    filled = int(pct / (100 / width))
    return f"[{'=' * filled}{'-' * (width - filled)}] {pct:5.1f}%  ({done:,}/{total:,})"


# ─────────────────────────────────────────────
#  Kernfunktion: paralleles Dispatching
# ─────────────────────────────────────────────

def _dispatch(world_path: str, dimension: str,
              task: str, task_kwargs: dict,
              num_workers: int) -> list:
    """
    Öffnet die Welt, gruppiert Chunks nach Region, verteilt Regionen
    an den Worker-Pool und sammelt die Ergebnisse ein.
    """
    level = amulet.load_level(world_path)
    print(list(level.dimensions))
    all_chunks = list(level.all_chunk_coords(dimension))
    world_name = Path(level.level_path).name
    level.close()

    if not all_chunks:
        return []

    regions = _group_chunks_by_region(all_chunks)

     # ── DEBUG: nur 1 Region pro Worker, und nur 3 Chunks pro Region ──
    selected_regions = list(regions.items())[:num_workers]
    regions = {
        region_key: coords[:3]
        for region_key, coords in selected_regions
    }
    # ────────────────────────────────────────────────────────────────
    total_regions = len(regions)
    total_chunks = len(all_chunks)

    print(f"\n  Welt:      {world_name}")
    print(f"  Dimension: {dimension}")
    print(f"  Chunks:    {total_chunks:,}  in  {total_regions:,} Regionen")
    print(f"  Worker:    {num_workers}")
    print()

    worker_args = [
        (dimension, coords, task, task_kwargs)
        for coords in regions.values()
    ]

    results = []
    done = 0

    with mp.Pool(processes=num_workers,
                 initializer=worker_init,
                 initargs=(world_path,)) as pool:
        for result in pool.imap_unordered(run_task, worker_args):
            results.append(result)
            done += 1
            print(f"  {_progress_bar(done, total_regions, 20)}", end="\r", flush=True)

    print(" " * 70, end="\r")
    #level.close()
    return results


# ─────────────────────────────────────────────
#  Öffentliche Manager-Funktionen
# ─────────────────────────────────────────────

def run_analyze_parallel(world_path: str, dimension: str,
                         num_workers: int) -> Counter:
    """
    Parallelisierte Welt-Analyse.
    Gibt einen Counter {block_id: count} zurück.
    """
    print(f"\n  Analysiere (parallel, {num_workers} Worker)...")

    results = _dispatch(
        world_path, dimension,
        task="analyze",
        task_kwargs={},
        num_workers=num_workers,
    )

    combined: Counter = Counter()
    for partial in results:
        combined.update(partial)

    return combined


def run_replace_parallel(world_path: str, dimension: str,
                         replacements: list, num_workers: int) -> int:
    """
    Parallelisiertes Block-Ersetzen.

    Ablauf:
      1. Worker finden in jeder Region welche Palette-Einträge ersetzt werden müssen
      2. Manager öffnet die Welt einmal zum Schreiben
      3. Manager schreibt alle markierten Chunks und speichert

    Gibt die Gesamtzahl ersetzter Blöcke zurück.
    """
    print(f"\n  Suche zu ersetzende Blöcke ({num_workers} Worker)...")

    results = _dispatch(
        world_path, dimension,
        task="replace",
        task_kwargs={"replacements": replacements},
        num_workers=num_workers,
    )

    all_swaps: dict = {}
    for partial in results:
        all_swaps.update(partial)

    chunks_to_write = len(all_swaps)
    if chunks_to_write == 0:
        print("  Keine Blöcke gefunden, die ersetzt werden müssen.\n")
        return 0

    print(f"  {chunks_to_write:,} Chunks enthalten zu ersetzende Blöcke.")
    print(f"\n  Schreibe Änderungen...")

    total_replaced = _write_replacements(world_path, dimension, all_swaps)
    return total_replaced


def _write_replacements(world_path: str, dimension: str, all_swaps: dict) -> int:
    """
    Öffnet die Welt zum Schreiben und ersetzt die markierten Blöcke.

    all_swaps: { (cx, cz): [(alter_palette_idx, neue_block_id_str), ...] }

    Gibt die Gesamtzahl ersetzter Blöcke zurück.
    """
    import numpy as np

    level = amulet.load_level(world_path)
    game_version = (level.level_wrapper.platform, level.level_wrapper.version)
    total_replaced = 0
    done = 0
    total = len(all_swaps)

    try:
        # Ziel-Blöcke vorab in Universal übersetzen (einmalig)
        target_universals: dict = {}  # block_id_str → universal_block
        for chunk_swaps in all_swaps.values():
            for _, new_id in chunk_swaps:
                if new_id not in target_universals:
                    try:
                        ns, name = new_id.split(":", 1)
                        versioned = Block(ns, name)
                        universal, _, _ = level.translation_manager.get_version(
                            *game_version
                        ).block.to_universal(versioned)
                        target_universals[new_id] = universal
                    except Exception:
                        target_universals[new_id] = None

        for (cx, cz), swaps in all_swaps.items():
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  {_progress_bar(done, total, 20)}  ersetzt: {total_replaced:,}",
                      end="\r", flush=True)

            try:
                chunk = level.get_chunk(cx, cz, dimension)
            except (ChunkLoadError, ChunkDoesNotExist):
                continue
            except Exception:
                continue

            try:
                blocks_array = chunk.blocks
                chunk_replaced = 0

                for old_idx, new_id in swaps:
                    universal = target_universals.get(new_id)
                    if universal is None:
                        continue

                    new_idx = chunk.block_palette.get_add_block(universal)
                    mask = blocks_array == old_idx
                    count = int(np.sum(mask))
                    if count > 0:
                        blocks_array[mask] = new_idx
                        chunk_replaced += count

                if chunk_replaced > 0:
                    chunk.changed = True
                    total_replaced += chunk_replaced

            except Exception:
                pass

        print(" " * 70, end="\r")
        print(f"  Speichere Welt...")
        level.save()

    finally:
        level.close()

    return total_replaced