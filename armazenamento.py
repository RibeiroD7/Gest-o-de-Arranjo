"""Resolução de caminhos de dados para desktop e mobile (Android/iOS).

No desktop o app grava em pastas relativas à sua própria pasta (`data/`,
`exports/`, `backups/`), como sempre. Quando empacotado pelo `flet build`
(Android/iOS ou desktop empacotado), o Flet define a variável
`FLET_APP_STORAGE_DATA` apontando para a área privada gravável do app — é lá
que passamos a gravar. Os arquivos que vêm embutidos no app (como o
`Temas.xlsx`) ficam somente-leitura em `FLET_ASSETS_DIR`.
"""

from __future__ import annotations

import os
from pathlib import Path

# Área gravável: definida pelo Flet em apps empacotados; senão, pasta local.
_STORAGE = os.environ.get("FLET_APP_STORAGE_DATA")
BASE_DIR = Path(_STORAGE) if _STORAGE else Path(".")

DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
BACKUPS_DIR = BASE_DIR / "backups"

# Pasta somente-leitura com os recursos embutidos (Temas.xlsx, ícones...).
_ASSETS = os.environ.get("FLET_ASSETS_DIR")
ASSETS_DIR = Path(_ASSETS) if _ASSETS else Path("assets")


def garantir_pastas() -> None:
    """Cria as pastas graváveis, se necessário."""
    for pasta in (DATA_DIR, EXPORTS_DIR, BACKUPS_DIR):
        pasta.mkdir(parents=True, exist_ok=True)


def caminho_temas_embutido() -> Path | None:
    """Procura o Temas.xlsx nos locais possíveis (gravável, assets, relativo)."""
    candidatos = [
        DATA_DIR / "Temas.xlsx",
        ASSETS_DIR / "Temas.xlsx",
        Path("assets") / "Temas.xlsx",
        Path("data") / "Temas.xlsx",
    ]
    return next((p for p in candidatos if p.exists()), None)


def caminho_temas_seed_json() -> Path | None:
    """Procura o temas_seed.json embutido (carga inicial dos temas sem Excel)."""
    candidatos = [
        ASSETS_DIR / "temas_seed.json",
        Path("assets") / "temas_seed.json",
    ]
    return next((p for p in candidatos if p.exists()), None)


def eh_mobile() -> bool:
    """True quando rodando empacotado num celular (área de storage definida)."""
    return _STORAGE is not None
