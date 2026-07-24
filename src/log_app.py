"""Registro de erros em arquivo, para diagnosticar problemas relatados.

Grava um ``gestao_arranjo.log`` rotativo na área gravável do app (a mesma do
banco) e captura exceções não tratadas. Defensivo: se algo falhar aqui, o app
segue normalmente — log nunca deve derrubar o programa.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from armazenamento import BASE_DIR

_CONFIGURADO = False
logger = logging.getLogger("gestao_arranjo")


def configurar_log() -> None:
    """Configura o log em arquivo e o gancho de exceções não tratadas."""
    global _CONFIGURADO
    if _CONFIGURADO:
        return
    try:
        arquivo = BASE_DIR / "gestao_arranjo.log"
        handler = RotatingFileHandler(
            arquivo, maxBytes=500_000, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        raiz = logging.getLogger()
        raiz.setLevel(logging.INFO)
        raiz.addHandler(handler)

        def _hook(tipo, valor, tb):
            logger.error("Erro não tratado", exc_info=(tipo, valor, tb))
            sys.__excepthook__(tipo, valor, tb)

        sys.excepthook = _hook
        _CONFIGURADO = True
    except Exception:  # noqa: BLE001 — log nunca deve quebrar o app
        pass
