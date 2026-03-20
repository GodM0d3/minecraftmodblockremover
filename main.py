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
    --version     Spielversion, z.B. "java,1,20,1" (standard: java,1,20,1)
    --top         Nur die N häufigsten Blöcke anzeigen (nur bei analyze)
    --parallel    Parallelisierung aktivieren (nur bei analyze)
    --workers     Anzahl der Worker-Prozesse (standard: 4, nur bei analyze)
"""

import sys
import argparse
import multiprocessing as mp

from utils import parse_version
from analyze import run_analyze
from config import run_config_menu
from replace import run_replace


DEFAULT_DIMENSION = "minecraft:overworld"
DEFAULT_VERSION = "java,1,20,1"
MAX_WORKERS = mp.cpu_count()


def print_banner() -> None:
    print("""
  ╔═══════════════════════════════════════╗
  ║     Minecraft Block Replacer          ║
  ╚═══════════════════════════════════════╝
    """)


def ask_parallel_options() -> tuple[bool, int]:
    """Fragt interaktiv ob Parallelisierung gewünscht ist und wie viele Worker."""
    use_parallel = input(f"  Parallelisierung verwenden? [j/N]: ").strip().lower()
    if use_parallel not in ("j", "ja", "y", "yes"):
        return False, 1

    print(f"  Verfügbare CPU-Kerne: {MAX_WORKERS}")
    workers_str = input(f"  Anzahl Worker [4]: ").strip()
    try:
        num_workers = int(workers_str) if workers_str else 4
        num_workers = max(1, min(num_workers, MAX_WORKERS))
    except ValueError:
        print("  Ungültige Eingabe, verwende 4 Worker.")
        num_workers = 4

    return True, num_workers


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
            world = input("\n  Pfad zur Welt: ").strip()
            dimension = input(f"  Dimension [{DEFAULT_DIMENSION}]: ").strip() or DEFAULT_DIMENSION
            version_str = input(f"  Version [{DEFAULT_VERSION}]: ").strip() or DEFAULT_VERSION
            top_str = input("  Top N Blöcke anzeigen (leer = alle): ").strip()
            top_n = int(top_str) if top_str.isdigit() else None
            parallel, num_workers = ask_parallel_options()

            try:
                game_version = parse_version(version_str)
                run_analyze(world, dimension, game_version,
                            top_n=top_n, parallel=parallel, num_workers=num_workers)
            except Exception as e:
                print(f"  Fehler: {e}")

        elif choice == "2":
            run_config_menu()

        elif choice == "3":
            world = input("\n  Pfad zur Welt: ").strip()
            dimension = input(f"  Dimension [{DEFAULT_DIMENSION}]: ").strip() or DEFAULT_DIMENSION
            version_str = input(f"  Version [{DEFAULT_VERSION}]: ").strip() or DEFAULT_VERSION
            try:
                game_version = parse_version(version_str)
                run_replace(world, dimension, game_version)
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
  python main.py analyze "~/saves/MeineWelt" --top 20
  python main.py analyze "~/saves/MeineWelt" --parallel
  python main.py analyze "~/saves/MeineWelt" --parallel --workers 16
  python main.py config
  python main.py replace "~/saves/MeineWelt"
  python main.py replace "~/saves/MeineWelt" --dimension minecraft:the_nether
        """
    )

    parser.add_argument(
        "mode",
        nargs="?",
        choices=["analyze", "config", "replace"],
        help="Modus: analyze | config | replace"
    )
    parser.add_argument("world", nargs="?", help="Pfad zum Welt-Ordner")
    parser.add_argument("--dimension", default=DEFAULT_DIMENSION)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--parallel", action="store_true",
                        help="Parallelisierung aktivieren (nur bei analyze)")
    parser.add_argument("--workers", type=int, default=4,
                        help=f"Anzahl Worker-Prozesse (standard: 4, max: {MAX_WORKERS})")

    args = parser.parse_args()

    # Kein Modus übergeben → interaktives Menü
    if args.mode is None:
        interactive_menu()
        return

    print_banner()

    try:
        game_version = parse_version(args.version)
    except Exception:
        print(f"  Fehler: Ungültiges Versionsformat '{args.version}'")
        print("  Beispiel: java,1,20,1  oder  bedrock,1,20,0")
        sys.exit(1)

    num_workers = max(1, min(args.workers, MAX_WORKERS))

    if args.mode == "analyze":
        if not args.world:
            print("  Fehler: Bitte Weltpfad angeben. Beispiel: python main.py analyze <welt>")
            sys.exit(1)
        run_analyze(args.world, args.dimension, game_version,
                    top_n=args.top, parallel=args.parallel, num_workers=num_workers)

    elif args.mode == "config":
        run_config_menu()

    elif args.mode == "replace":
        if not args.world:
            print("  Fehler: Bitte Weltpfad angeben. Beispiel: python main.py replace <welt>")
            sys.exit(1)
        run_replace(args.world, args.dimension, game_version)


if __name__ == "__main__":
    main()