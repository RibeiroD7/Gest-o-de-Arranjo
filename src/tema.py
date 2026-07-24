"""Identidade visual e medidas do app (tema "Meia-noite teal").

Valores puros (sem Flet), reutilizados pelas telas. Centralizá-los aqui é o
primeiro passo da modularização do ``main.py`` e a base para futuros ajustes
de acessibilidade (escala de fonte / tema claro).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Acessibilidade: escala de fonte
# ---------------------------------------------------------------------------
# `fonte(n)` devolve o tamanho já escalado; as telas usam isso no lugar dos
# números fixos. As larguras fixas de coluna acompanham a escala (senão o
# texto maior seria cortado) — por isso são recalculadas em `definir_escala`
# e devem ser lidas como `tema.LARGURA_...` (atributo do módulo), nunca
# importadas por valor.

ESCALA_MIN = 0.9
ESCALA_MAX = 1.6
_ESCALA = 1.0

# Valores base (escala 1.0) das medidas que acompanham a fonte.
_MEDIDAS_BASE = {
    "LARGURA_BARRA_LATERAL": 192,
    "ICON_SIZE_MENU": 18,
    "LARGURA_COL_DATA_MES": 76,
    "LARGURA_COL_ORADOR_MES": 150,
    "LARGURA_COL_ACOES_MES": 80,
    "LARGURA_COL_TEMA_MES": 150,
    "ALTURA_CONTEUDO_DIALOG_MES": 480,
}


def escala_atual() -> float:
    """Fator de escala de fonte em uso (1.0 = tamanho padrão)."""
    return _ESCALA


def definir_escala(valor: float) -> None:
    """Define a escala de fonte e recalcula as medidas que dependem dela."""
    global _ESCALA
    _ESCALA = max(ESCALA_MIN, min(ESCALA_MAX, round(float(valor), 2)))
    for nome, base in _MEDIDAS_BASE.items():
        globals()[nome] = round(base * _ESCALA)


def fonte(tamanho: float) -> int:
    """Tamanho de texto/ícone já ajustado pela escala escolhida."""
    return max(8, round(tamanho * _ESCALA))


# Barra lateral / menu (recalculados por definir_escala)
LARGURA_BARRA_LATERAL = 192
ICON_SIZE_MENU = 18

# Cores — "Meia-noite teal": azul profundo com acento verde-água
COR_DESTAQUE = "#14B8A6"
COR_DESTAQUE_CLARA = "#2DD4BF"
COR_DESTAQUE_SUAVE = "#5EEAD4"

FUNDO_APP = "#0E1524"
FUNDO_SIDEBAR = "#121A2E"
FUNDO_CARD = "#16223B"
FUNDO_ELEVADO = "#1C2A47"

TEXTO_PRIMARIO = "#E7ECF5"
TEXTO_SECUNDARIO = "#7C89A6"
BORDA_SUAVE = "#24304E"

COR_SUCESSO = "#34D399"
COR_AVISO = "#FBBF24"
COR_ERRO = "#F87171"

# Prévia do Quadro de Anúncios (PC): largura base em pixels e limites de zoom.
# O PNG é gerado a LARGURA_PREVIEW_BASE * 3 px, então ampliar até 300% continua
# nítido sem regerar a imagem.
LARGURA_PREVIEW_BASE = 620
ZOOM_PREVIEW_MIN = 0.5
ZOOM_PREVIEW_MAX = 3.0

# Diálogo / tabela do mês
LARGURA_DIALOG_MES = 1040
ALTURA_CONTEUDO_DIALOG_MES = 480
LARGURA_COL_DATA_MES = 76
LARGURA_COL_ORADOR_MES = 150
LARGURA_COL_ACOES_MES = 80
LARGURA_COL_TEMA_MES = 150  # largura fixa no celular (tabela rola na horizontal)
ESPACO_COLUNAS_MES = 8
