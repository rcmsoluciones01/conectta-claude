"""Empaqueta la skill para subirla a claude.ai.

    python scripts/empaquetar_zip.py

Deja dist/conectar-con-conectta.zip con la carpeta de la skill dentro
(conectar-con-conectta/SKILL.md, references/, assets/), que es lo que pide
claude.ai. Volver a ejecutarlo tras cada cambio de la skill.
"""

import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SKILL = RAIZ / "plugins" / "conectta" / "skills" / "conectar-con-conectta"
DESTINO = RAIZ / "dist" / f"{SKILL.name}.zip"
IGNORAR = {"__pycache__", ".DS_Store", "node_modules"}


def main() -> None:
    if not (SKILL / "SKILL.md").is_file():
        raise SystemExit(f"No encuentro {SKILL / 'SKILL.md'}")
    DESTINO.parent.mkdir(exist_ok=True)
    archivos = sorted(p for p in SKILL.rglob("*") if p.is_file() and not IGNORAR.intersection(p.parts))
    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_DEFLATED) as zip_:
        for archivo in archivos:
            zip_.write(archivo, Path(SKILL.name) / archivo.relative_to(SKILL))
    print(f"{DESTINO.relative_to(RAIZ)}: {len(archivos)} archivos")


if __name__ == "__main__":
    main()
