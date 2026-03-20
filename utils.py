"""
Hilfsfunktionen für den Minecraft Block Replacer.
"""
 
 
def parse_version(version_str: str) -> tuple:
    """Parst einen Versions-String wie 'java,1,20,1' in ein amulet-Versions-Tupel."""
    parts = version_str.split(",")
    platform = parts[0].strip()
    nums = tuple(int(p) for p in parts[1:])
    return (platform, nums)
 
 
def ensure_namespace(block_id: str) -> str:
    """Stellt sicher, dass eine Block-ID einen Namespace hat (z.B. 'minecraft:stone')."""
    return block_id if ":" in block_id else f"minecraft:{block_id}"
 