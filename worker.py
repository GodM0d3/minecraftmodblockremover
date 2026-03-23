"""
Worker-Modul für den Minecraft Block Replacer.

Jeder Worker-Prozess:
  - öffnet die Welt EINMAL beim Start (via Pool-Initializer)
  - verarbeitet beliebig viele Regionen aus der Pool-Queue
  - schließt die Welt wenn der Prozess endet

Unterstützte Tasks (als String übergeben, nicht als Funktion):
  "analyze"  → gibt dict {block_id: count} zurück
  "replace"  → gibt dict {(cx, cz): [(old_idx, new_id), ...]} zurück
"""

from collections import Counter
import sys

import numpy as np
import amulet
from amulet.api.block import Block
from amulet.api.errors import ChunkLoadError, ChunkDoesNotExist


# ─────────────────────────────────────────────
#  Prozess-globales Level (einmal pro Worker)
# ─────────────────────────────────────────────

_level = None   # wird durch worker_init() gesetzt


def worker_init(world_path: str) -> None:
    global _level
    _level = amulet.load_level(world_path)
    coords = list(_level.all_chunk_coords("minecraft:overworld"))
    print(f"  [Worker] Chunks im Worker: {len(coords)}", file=sys.stderr)
    if coords:
        cx, cz = coords[0]
        try:
            chunk = _level.get_chunk(cx, cz, "minecraft:overworld")
            print(f"  [Worker] Test-Chunk OK: ({cx}, {cz})", file=sys.stderr)
        except Exception as e:
            print(f"  [Worker] Test-Chunk fehlgeschlagen: {type(e).__name__}: {e}", file=sys.stderr)


# ─────────────────────────────────────────────
#  Hilfsfunktionen
# ─────────────────────────────────────────────

def _make_cache_key(universal_block) -> tuple:
    """Eindeutiger Cache-Key: Name + Properties (verhindert falsche Cache-Hits)."""
    props = tuple(sorted(universal_block.properties.items())) \
        if hasattr(universal_block, "properties") else ()
    return (universal_block.namespaced_name, props)


def _translate_palette(palette, version_obj, cache: dict) -> list:
    """
    Übersetzt alle Einträge einer Chunk-Palette einmalig.
    Nutzt einen lokalen Cache pro Worker – kein geteilter State, kein Locking.
    Gibt eine Liste zurück: Index i → übersetzte Block-ID als String.
    """
    result = []
    for i in range(len(palette)):
        universal_block = palette[i]
        key = _make_cache_key(universal_block)

        if key not in cache:
            try:
                versioned_block, _ = version_obj.from_universal(universal_block)
                cache[key] = (
                    versioned_block.namespaced_name
                    if isinstance(versioned_block, Block)
                    else universal_block.namespaced_name
                )
            except Exception:
                cache[key] = universal_block.namespaced_name

        result.append(cache[key])
    return result


# ─────────────────────────────────────────────
#  Task-Implementierungen
# ─────────────────────────────────────────────

def _task_analyze(chunk_coords: list, dimension: str) -> dict:
    if _level is None:
        print(f"Level is none, abort", file=sys.stderr)
        return
    """Zählt alle Blocktypen in den gegebenen Chunks."""
    game_version = (_level.level_wrapper.platform, _level.level_wrapper.version)
    version_obj = _level.translation_manager.get_version(*game_version).block
    cache: dict = {}
    block_counts: Counter = Counter()
    for cx, cz in chunk_coords:
        try:
            chunk = _level.get_chunk(cx, cz, dimension)
        except ChunkDoesNotExist as e:
            print(f"  [Worker] ChunkDoesNotExist at ({cx}, {cz}): {e}", file=sys.stderr)
            continue
        except ChunkLoadError as e:
            print(f"  [Worker] ChunkLoadError at ({cx}, {cz}): {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"  [Worker] Fehler beim Laden von ({cx}, {cz}): {e}", file=sys.stderr)
            continue
        
        print(f"  [Worker] MManaged to get Chunk ({cx}, {cz})", file=sys.stderr)

        try:
            blocks_array = chunk.blocks
            palette = chunk.block_palette
            palette_len = len(palette)

            translated = _translate_palette(palette, version_obj, cache)

            flat = blocks_array.ravel()
            bc = np.bincount(flat, minlength=palette_len)

            for idx, count in enumerate(bc):
                if count > 0:
                    block_counts[translated[idx]] += int(count)

        except Exception as e:
            print(f"  [Worker] Fehler beim Verarbeiten von ({cx}, {cz}): {e}", file=sys.stderr)

    return dict(block_counts)


def _task_replace(chunk_coords: list, dimension: str, replacements: list) -> dict:
    """
    Findet alle zu ersetzenden Blöcke in den gegebenen Chunks.
    Gibt { (cx, cz): [(alter_palette_idx, neue_block_id), ...] } zurück.
    Der Manager schreibt die Chunks anschließend selbst.
    """
    game_version = (_level.level_wrapper.platform, _level.level_wrapper.version)
    version_obj = _level.translation_manager.get_version(*game_version).block
    cache: dict = {}

    from_ids = {entry["from"] for entry in replacements}
    from_to  = {entry["from"]: entry["to"] for entry in replacements}

    result: dict = {}

    for cx, cz in chunk_coords:
        try:
            chunk = _level.get_chunk(cx, cz, dimension)
        except ChunkDoesNotExist as e:
            print(f"  [Worker] ChunkDoesNotExist at ({cx}, {cz}): {e}", file=sys.stderr)
            continue
        except ChunkLoadError as e:
            print(f"  [Worker] ChunkLoadError at ({cx}, {cz}): {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"  [Worker] Fehler beim Laden von ({cx}, {cz}): {e}", file=sys.stderr)
            continue

        try:
            palette = chunk.block_palette
            translated = _translate_palette(palette, version_obj, cache)

            swaps = [
                (idx, from_to[block_id])
                for idx, block_id in enumerate(translated)
                if block_id in from_ids
            ]

            if swaps:
                result[(cx, cz)] = swaps

        except Exception as e:
            print(f"  [Worker] Fehler beim Verarbeiten von ({cx}, {cz}): {e}", file=sys.stderr)

    return result


# ─────────────────────────────────────────────
#  Öffentlicher Task-Einstiegspunkt
# ─────────────────────────────────────────────

_TASKS = {
    "analyze": _task_analyze,
    "replace": _task_replace,
}


def run_task(args: tuple):
    """
    Wird von Pool.imap_unordered aufgerufen — einmal pro Region.
    Das Level ist bereits geöffnet (_level), kein load/close hier.

    args = (dimension, chunk_coords, task, task_kwargs)
    """
    if _level is None:
        return {}

    dimension, chunk_coords, task, task_kwargs = args

    if task not in _TASKS:
        return {}

    try:
        return _TASKS[task](chunk_coords, dimension, **task_kwargs)
    except Exception as e:
        print(f"  [Worker] Fehler in Region: {e}", file=sys.stderr)
        return {}