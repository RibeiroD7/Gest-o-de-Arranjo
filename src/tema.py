"""Identidade visual e medidas do app (tema "Meia-noite teal").

Valores puros (sem Flet), reutilizados pelas telas. Centralizá-los aqui é o
primeiro passo da modularização do ``main.py`` e a base para futuros ajustes
de acessibilidade (escala de fonte / tema claro).
"""

from __future__ import annotations

# Barra lateral / menu
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

# Diálogo / tabela do mês
LARGURA_DIALOG_MES = 1040
ALTURA_CONTEUDO_DIALOG_MES = 480
LARGURA_COL_DATA_MES = 76
LARGURA_COL_ORADOR_MES = 150
LARGURA_COL_ACOES_MES = 80
LARGURA_COL_TEMA_MES = 150  # largura fixa no celular (tabela rola na horizontal)
ESPACO_COLUNAS_MES = 8
