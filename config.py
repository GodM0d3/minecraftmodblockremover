"""
Verwaltung der Block-Ersetzungsliste (blocks.json).
"""

import json
from pathlib import Path

CONFIG_FILE = Path("blocks.json")


def load_config() -> list:
    """Lädt die Ersetzungsliste aus der JSON-Datei."""
    if not CONFIG_FILE.exists():
        return []
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("replacements", [])


def save_config(replacements: list) -> None:
    """Speichert die Ersetzungsliste in die JSON-Datei."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"replacements": replacements}, f, indent=4, ensure_ascii=False)


def show_config(replacements: list) -> None:
    """Gibt die aktuelle Ersetzungsliste aus."""
    if not replacements:
        print("\n  Die Ersetzungsliste ist leer.\n")
        return

    print(f"\n  {'#':<5} {'Von':<45} {'Nach':<45}")
    print(f"  {'-'*5} {'-'*45} {'-'*45}")
    for i, entry in enumerate(replacements, 1):
        print(f"  {i:<5} {entry['from']:<45} {entry['to']:<45}")
    print()


def add_entry(replacements: list) -> list:
    """Fügt einen neuen Eintrag zur Ersetzungsliste hinzu."""
    print("\n  Neuen Eintrag hinzufügen:")
    old = input("    Alter Block (z.B. minecraft:stone): ").strip()
    new = input("    Neuer Block (z.B. minecraft:diamond_block): ").strip()

    if not old or not new:
        print("  Abgebrochen – leere Eingabe.")
        return replacements

    # Namespace ergänzen falls nötig
    if ":" not in old:
        old = f"minecraft:{old}"
    if ":" not in new:
        new = f"minecraft:{new}"

    # Duplikat prüfen
    for entry in replacements:
        if entry["from"] == old:
            print(f"  '{old}' ist bereits in der Liste (-> {entry['to']}).")
            overwrite = input("  Überschreiben? [j/N]: ").strip().lower()
            if overwrite in ("j", "ja", "y", "yes"):
                entry["to"] = new
                print(f"  Aktualisiert: '{old}' -> '{new}'")
            return replacements

    replacements.append({"from": old, "to": new})
    print(f"  Hinzugefügt: '{old}' -> '{new}'")
    return replacements


def delete_entry(replacements: list) -> list:
    """Löscht einen Eintrag aus der Ersetzungsliste."""
    if not replacements:
        print("\n  Die Liste ist bereits leer.\n")
        return replacements

    show_config(replacements)
    try:
        idx = int(input("  Nummer des zu löschenden Eintrags (0 = Abbrechen): ").strip())
    except ValueError:
        print("  Ungültige Eingabe.")
        return replacements

    if idx == 0:
        print("  Abgebrochen.")
        return replacements

    if 1 <= idx <= len(replacements):
        removed = replacements.pop(idx - 1)
        print(f"  Gelöscht: '{removed['from']}' -> '{removed['to']}'")
    else:
        print("  Ungültige Nummer.")

    return replacements


def clear_config(replacements: list) -> list:
    """Löscht die gesamte Ersetzungsliste."""
    confirm = input("\n  Wirklich ALLE Einträge löschen? [j/N]: ").strip().lower()
    if confirm in ("j", "ja", "y", "yes"):
        print("  Liste geleert.")
        return []
    print("  Abgebrochen.")
    return replacements


def run_config_menu() -> None:
    """Interaktives Menü zur Verwaltung der Ersetzungsliste."""
    replacements = load_config()

    while True:
        print("\n  ╔══════════════════════════════╗")
        print("  ║     Ersetzungsliste (config) ║")
        print("  ╠══════════════════════════════╣")
        print("  ║  1 - Liste anzeigen          ║")
        print("  ║  2 - Eintrag hinzufügen      ║")
        print("  ║  3 - Eintrag löschen         ║")
        print("  ║  4 - Alle Einträge löschen   ║")
        print("  ║  0 - Zurück / Beenden        ║")
        print("  ╚══════════════════════════════╝")

        choice = input("\n  Auswahl: ").strip()

        if choice == "1":
            show_config(replacements)
        elif choice == "2":
            replacements = add_entry(replacements)
            save_config(replacements)
        elif choice == "3":
            replacements = delete_entry(replacements)
            save_config(replacements)
        elif choice == "4":
            replacements = clear_config(replacements)
            save_config(replacements)
        elif choice == "0":
            break
        else:
            print("  Ungültige Auswahl.")