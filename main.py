"""
Minecraft Block Replacer
========================
Analysiert eine Minecraft-Welt, verwaltet eine Block-Ersetzungsliste
und ersetzt Blöcke in der Welt anhand dieser Liste.

Verwendung:
    python main.py                          # Interaktives Menü
    python main.py analyze <welt>           # Welt analysieren
    python main.py config                   # Ersetzungsliste verwalten
    python main.py replace <welt>           # Blöcke ersetzen

Optionen:
    --dimension   Dimension (standard: minecraft:overworld)
    --workers     Anzahl der Worker-Prozesse (standard: 4)
"""

import sys
import argparse
import multiprocessing as mp

from analyze import run_analyze
from config import run_config_menu
from replace import run_replace


DEFAULT_DIMENSION = "minecraft:overworld"
MAX_WORKERS       = mp.cpu_count()


def print_banner() -> None:
    print("""
  ╔═══════════════════════════════════════╗
  ║     Minecraft Block Replacer          ║
  ╚═══════════════════════════════════════╝
    """)


def ask_workers() -> int:
    """Fragt interaktiv nach der Anzahl der Worker-Prozesse."""
    print(f"  Verfügbare CPU-Kerne: {MAX_WORKERS}")
    workers_str = input("  Anzahl Worker [4]: ").strip()
    try:
        num_workers = int(workers_str) if workers_str else 4
        return max(1, min(num_workers, MAX_WORKERS))
    except ValueError:
        print("  Ungültige Eingabe, verwende 4 Worker.")
        return 4


def ask_dimension(world_path: str) -> str:
    """
    Liest verfügbare Dimensionen aus der Welt und lässt den Nutzer eine auswählen.
    Gibt die gewählte Dimension zurück, oder None bei Fehler.
    """
    import amulet
    from pathlib import Path

    path = Path(world_path).expanduser().resolve()
    if not path.exists():
        print(f"  Fehler: Pfad nicht gefunden: {path}")
        return None

    try:
        level = amulet.load_level(str(path))
        dimensions = sorted(level.dimensions)
        level.close()
    except Exception as e:
        print(f"  Fehler beim Laden der Welt: {e}")
        return None

    print(f"\n  Verfügbare Dimensionen:")
    for i, dim in enumerate(dimensions, 1):
        print(f"    {i} – {dim}")

    choice = input("\n  Dimension wählen [1]: ").strip()
    try:
        idx = int(choice) - 1 if choice else 0
        if 0 <= idx < len(dimensions):
            return dimensions[idx]
        print("  Ungültige Auswahl.")
        return None
    except ValueError:
        print("  Ungültige Eingabe.")
        return None


def interactive_menu() -> None:
    """Interaktives Hauptmenü wenn kein Argument übergeben wurde."""
    print_banner()

    while True:
        print("  ╔══════════════════════════════╗")
        print("  ║          Hauptmenü           ║")
        print("  ╠══════════════════════════════╣")
        print("  ║  1 – Welt analysieren        ║")
        print("  ║  2 – Ersetzungsliste         ║")
        print("  ║  3 – Blöcke ersetzen         ║")
        print("  ║  0 – Beenden                 ║")
        print("  ╚══════════════════════════════╝")

        choice = input("\n  Auswahl: ").strip()

        if choice == "1":
            world       = input("\n  Pfad zur Welt: ").strip()
            dimension   = ask_dimension(world)
            if dimension is None:
                continue
            num_workers = ask_workers()
            try:
                run_analyze(world, dimension, num_workers=num_workers)
            except Exception as e:
                print(f"  Fehler: {e}")

        elif choice == "2":
            run_config_menu()

        elif choice == "3":
            world       = input("\n  Pfad zur Welt: ").strip()
            dimension   = ask_dimension(world)
            if dimension is None:
                continue
            num_workers = ask_workers()
            try:
                run_replace(world, dimension, num_workers=num_workers)
            except Exception as e:
                print(f"  Fehler: {e}")

        elif choice == "0":
            print("\n  Ende\n")
            break

        else:
            print("  Ungültige Auswahl.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Minecraft Block Replacer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python main.py
  python main.py analyze "~/saves/MeineWelt"
  python main.py config
  python main.py replace "~/saves/MeineWelt" --workers 8 --dimension minecraft:the_nether
        """
    )

    parser.add_argument(
        "mode",
        nargs="?",
        choices=["analyze", "config", "replace"],
        help="Modus: analyze | config | replace",
    )
    parser.add_argument("world",        nargs="?", help="Pfad zum Welt-Ordner")
    parser.add_argument("--dimension",  default=DEFAULT_DIMENSION)
    parser.add_argument("--workers",    type=int, default=4,
                        help=f"Anzahl Worker-Prozesse (standard: 4, max: {MAX_WORKERS})")

    args = parser.parse_args()

    if args.mode is None:
        interactive_menu()
        return

    print_banner()

    num_workers = max(1, min(args.workers, MAX_WORKERS))

    if args.mode == "analyze":
        if not args.world:
            print("  Fehler: Bitte Weltpfad angeben.")
            sys.exit(1)
        run_analyze(args.world, args.dimension, num_workers=num_workers)

    elif args.mode == "config":
        run_config_menu()

    elif args.mode == "replace":
        if not args.world:
            print("  Fehler: Bitte Weltpfad angeben.")
            sys.exit(1)
        run_replace(args.world, args.dimension, num_workers=num_workers)


if __name__ == "__main__":
    main()