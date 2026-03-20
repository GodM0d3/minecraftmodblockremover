"""
Analyse einer Minecraft-Welt mit amulet-core.
Zählt alle Blocktypen und gibt eine sortierte Liste aus.
Speichert das Ergebnis zusätzlich als JSON-Datei.
Unterstützt optionale Parallelisierung via multiprocessing.
"""

from collections import Counter
from pathlib import Path
import multiprocessing as mp
import json
import datetime

try:
    import amulet
    from amulet.api.block import Block
    from amulet.api.errors import ChunkLoadError, ChunkDoesNotExist
except ImportError:
    print("Bitte zuerst amulet-core installieren: pip install amulet-core")
    raise


# ─────────────────────────────────────────────
#  JSON-Export
# ─────────────────────────────────────────────

def save_analysis_json(block_counts: Counter, world_path: str,
                       dimension: str, game_version: tuple) -> Path:
    """Speichert die Analyse als JSON-Datei."""
    world_name = Path(world_path).name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"analysis_{world_name}_{timestamp}.json"
    output_path = Path(filename)

    total_blocks = sum(block_counts.values())

    data = {
        "meta": {
            "world": world_name,
            "world_path": str(world_path),
            "dimension": dimension,
            "game_version": list(game_version),
            "analyzed_at": datetime.datetime.now().isoformat(),
            "total_blocks": total_blocks,
            "unique_block_types": len(block_counts),
        },
        "blocks": [
            {
                "id": block_id,
                "count": count,
                "percent": round(count / total_blocks * 100, 4)
            }
            for block_id, count in block_counts.most_common()
        ]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path


# ─────────────────────────────────────────────
#  Worker für Parallelisierung
# ─────────────────────────────────────────────

def _worker(args):
    """
    Wird in einem separaten Prozess ausgeführt.
    Meldet Fortschritt über eine Queue zurück.
    """
    world_path, dimension, game_version, chunk_coords, progress_queue = args

    try:
        import numpy as np
        import amulet
        from amulet.api.block import Block
        from amulet.api.errors import ChunkLoadError, ChunkDoesNotExist

        level = amulet.load_level(world_path)
        block_counts = Counter()
        report_every = max(1, len(chunk_coords) // 20)
        translation_cache = {}

        for i, (cx, cz) in enumerate(chunk_coords):
            if i % report_every == 0:
                progress_queue.put(report_every)

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
                        key = universal_block.namespaced_name

                        if key not in translation_cache:
                            versioned_block, _ = level.translation_manager.get_version(
                                *game_version
                            ).block.from_universal(universal_block)
                            translation_cache[key] = (
                                versioned_block.namespaced_name
                                if isinstance(versioned_block, Block)
                                else key
                            )

                        block_counts[translation_cache[key]] += int(count)
                    except Exception:
                        pass
            except Exception:
                pass

        level.close()
        progress_queue.put(None)
        return dict(block_counts)

    except Exception:
        progress_queue.put(None)
        return {}


# ─────────────────────────────────────────────
#  Analyse-Funktionen
# ─────────────────────────────────────────────

def analyze_world(level, dimension: str, game_version: tuple) -> Counter:
    """Single-threaded Analyse mit Translation-Cache."""
    import numpy as np

    block_counts = Counter()
    all_chunks = list(level.all_chunk_coords(dimension))
    total = len(all_chunks)
    translation_cache = {}

    if total == 0:
        print(f"  Keine Chunks in Dimension '{dimension}' gefunden.")
        return block_counts

    print(f"\n  Welt:      {Path(level.level_path).name}")
    print(f"  Dimension: {dimension}")
    print(f"  Chunks:    {total:,}")
    print(f"\n  Analysiere (single-threaded)...\n")

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
                    key = universal_block.namespaced_name

                    if key not in translation_cache:
                        versioned_block, _ = level.translation_manager.get_version(
                            *game_version
                        ).block.from_universal(universal_block)
                        translation_cache[key] = (
                            versioned_block.namespaced_name
                            if isinstance(versioned_block, Block)
                            else key
                        )

                    block_counts[translation_cache[key]] += int(count)
                except Exception:
                    pass
        except Exception:
            pass

    print(" " * 70, end="\r")
    return block_counts


def analyze_world_parallel(world_path: str, dimension: str, game_version: tuple,
                            num_workers: int) -> Counter:
    """Parallelisierte Analyse mit Echtzeit-Fortschrittsbalken."""
    print(f"\n  Lade Chunk-Liste...")
    level = amulet.load_level(world_path)
    all_chunks = list(level.all_chunk_coords(dimension))
    total = len(all_chunks)
    world_name = Path(level.level_path).name
    level.close()

    if total == 0:
        print(f"  Keine Chunks in Dimension '{dimension}' gefunden.")
        return Counter()

    print(f"\n  Welt:      {world_name}")
    print(f"  Dimension: {dimension}")
    print(f"  Chunks:    {total:,}")
    print(f"  Worker:    {num_workers}")
    print(f"\n  Analysiere (parallel)...\n")

    chunk_size = max(1, total // num_workers)
    batches = [all_chunks[i:i + chunk_size] for i in range(0, total, chunk_size)]

    manager = mp.Manager()
    progress_queue = manager.Queue()

    worker_args = [(world_path, dimension, game_version, batch, progress_queue)
                   for batch in batches]

    combined = Counter()
    processed = 0
    finished_workers = 0

    with mp.Pool(processes=num_workers) as pool:
        result_iter = pool.imap_unordered(_worker, worker_args)

        while finished_workers < len(batches):
            try:
                msg = progress_queue.get(timeout=0.1)
                if msg is None:
                    finished_workers += 1
                else:
                    processed += msg

                pct = min(processed / total * 100, 100)
                bar = "=" * int(pct / 5) + "-" * (20 - int(pct / 5))
                print(f"  [{bar}] {pct:5.1f}%  ({processed:,}/{total:,} Chunks)", end="\r", flush=True)

            except Exception:
                pass

        for result in result_iter:
            combined.update(result)

    print(" " * 70, end="\r")
    return combined


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
#  Einstiegspunkt
# ─────────────────────────────────────────────

def run_analyze(world_path: str, dimension: str, game_version: tuple,
                top_n=None, parallel: bool = False, num_workers: int = 4) -> Counter:
    """
    Lädt die Welt, analysiert sie, gibt Ergebnis aus und speichert JSON.
    """
    path = Path(world_path).expanduser().resolve()
    if not path.exists():
        print(f"  Fehler: Pfad nicht gefunden: {path}")
        return Counter()

    if parallel:
        block_counts = analyze_world_parallel(
            str(path), dimension, game_version, num_workers=num_workers
        )
    else:
        print(f"\n  Lade Welt...")
        try:
            level = amulet.load_level(str(path))
        except Exception as e:
            print(f"  Fehler: Konnte Welt nicht laden: {e}")
            return Counter()
        try:
            block_counts = analyze_world(level, dimension, game_version)
        finally:
            level.close()

    print_analysis(block_counts, top_n=top_n)

    # JSON speichern
    if block_counts:
        try:
            json_path = save_analysis_json(block_counts, str(path), dimension, game_version)
            print(f"  Analyse gespeichert: {json_path}\n")
        except Exception as e:
            print(f"  Warnung: JSON konnte nicht gespeichert werden: {e}\n")

    return block_counts