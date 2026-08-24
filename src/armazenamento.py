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
# Fotos dos contatos vinculados. Ficam FORA do backup de propósito: são só
# enfeite, pesariam no arquivo enviado à nuvem todo dia e voltam sozinhas do
# aparelho na próxima sincronização.
FOTOS_DIR = DATA_DIR / "fotos"

# Pasta somente-leitura com os recursos embutidos (Temas.xlsx, ícones...).
_ASSETS = os.environ.get("FLET_ASSETS_DIR")
ASSETS_DIR = Path(_ASSETS) if _ASSETS else Path("assets")


def garantir_pastas() -> None:
    """Cria as pastas graváveis, se necessário."""
    for pasta in (DATA_DIR, EXPORTS_DIR, BACKUPS_DIR, FOTOS_DIR):
        pasta.mkdir(parents=True, exist_ok=True)


# Layout em uso. Começa em desktop e só muda quando o main descobre a
# plataforma real. O padrão aqui existe para quem chamar eh_mobile() antes
# disso (um teste, um script) receber uma resposta em vez de NameError.
_LAYOUT_MOBILE = False


def definir_layout_mobile(mobile: bool) -> None:
    """Define se a interface deve usar o layout de celular (Android/iOS)."""
    global _LAYOUT_MOBILE
    _LAYOUT_MOBILE = bool(mobile)


def eh_mobile() -> bool:
    """True quando a INTERFACE deve usar o layout de celular.

    Vem da plataforma real (definida por ``definir_layout_mobile`` no main).
    GA_FORCAR_MOBILE=1 força o layout de celular no computador, para testes.
    Não confundir com a área de armazenamento: o desktop empacotado também
    grava em FLET_APP_STORAGE_DATA, mas continua sendo desktop.
    """
    if os.environ.get("GA_FORCAR_MOBILE") == "1":
        return True
    return bool(_LAYOUT_MOBILE)
