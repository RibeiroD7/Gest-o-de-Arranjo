"""Componentes e helpers de interface reutilizados por todas as telas.

Fatia 2 da modularização do ``main.py``. Aqui só entram funções de UI **sem
estado do app**: dependem apenas do tema (``tema.py``), da plataforma
(``armazenamento.eh_mobile``) e do Flet — nunca do ``main``. Isso quebra o
ciclo de imports e permite que cada tela, ao ser extraída, importe daqui.
"""

from __future__ import annotations

import webbrowser
from typing import Callable

import flet as ft

from armazenamento import eh_mobile
from tema import (
    BORDA_SUAVE,
    COR_DESTAQUE,
    COR_DESTAQUE_CLARA,
    COR_DESTAQUE_SUAVE,
    COR_ERRO,
    FUNDO_APP,
    FUNDO_CARD,
    FUNDO_ELEVADO,
    FUNDO_SIDEBAR,
    TEXTO_PRIMARIO,
    TEXTO_SECUNDARIO,
    fonte,
)

# ---------------------------------------------------------------------------
# Tema e estilos
# ---------------------------------------------------------------------------


def aplicar_tema(page: ft.Page) -> None:
    """Aplica o tema "Meia-noite teal" (azul profundo com acento verde-água)."""
    esquema = ft.ColorScheme(
        primary=COR_DESTAQUE,
        on_primary="#04342C",
        primary_container="#0F3D3A",
        on_primary_container=COR_DESTAQUE_SUAVE,
        secondary=COR_DESTAQUE_CLARA,
        on_secondary="#04342C",
        surface=FUNDO_APP,
        on_surface=TEXTO_PRIMARIO,
        on_surface_variant=TEXTO_SECUNDARIO,
        surface_container_lowest=FUNDO_APP,
        surface_container_low=FUNDO_SIDEBAR,
        surface_container=FUNDO_CARD,
        surface_container_high=FUNDO_ELEVADO,
        surface_container_highest="#233250",
        outline=BORDA_SUAVE,
        outline_variant="#1E2942",
        error=COR_ERRO,
    )
    tema = ft.Theme(color_scheme=esquema, use_material3=True)
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = tema
    page.dark_theme = tema
    page.bgcolor = FUNDO_APP


def _sombra_card(intensidade: float = 0.35) -> ft.BoxShadow:
    """Sombra suave para cards no modo escuro."""
    return ft.BoxShadow(
        blur_radius=16,
        spread_radius=0,
        color=ft.Colors.with_opacity(intensidade, "#000000"),
        offset=ft.Offset(0, 4),
    )


def _estilo_campo_busca() -> dict:
    """Estilo compartilhado dos campos de busca."""
    return {
        "border_radius": 10,
        "height": 44,
        "content_padding": ft.Padding.symmetric(horizontal=12),
        "bgcolor": FUNDO_ELEVADO,
        "border_color": BORDA_SUAVE,
        "focused_border_color": COR_DESTAQUE,
        "cursor_color": COR_DESTAQUE,
        "color": TEXTO_PRIMARIO,
    }


def _cor_fundo_item_menu(selecionado: bool):
    """Fundo suave e arredondado para o item selecionado."""
    if selecionado:
        return ft.Colors.with_opacity(0.14, COR_DESTAQUE_CLARA)
    return ft.Colors.TRANSPARENT


# ---------------------------------------------------------------------------
# Blocos de tela
# ---------------------------------------------------------------------------


def criar_secao_titulo(texto: str) -> ft.Text:
    """Subtítulo de seção usado em todas as telas."""
    return ft.Text(texto, size=fonte(16), weight=ft.FontWeight.W_600, color=TEXTO_PRIMARIO)


def criar_cabecalho_tela(
    titulo: str,
    subtitulo: str = "",
    subtitulo_no_celular: bool = False,
) -> ft.Column:
    """Cabeçalho padronizado de cada tela (compacto no celular)."""
    mobile = eh_mobile()
    if mobile and not subtitulo_no_celular:
        # A barra superior já mostra o nome da seção; repetir o título aqui
        # só rouba espaço da tabela/lista. Telas com informação real no
        # cabeçalho (o Início) usam subtitulo_no_celular=True.
        return ft.Column([], spacing=0, tight=True)
    controles = [
        ft.Text(
            titulo,
            size=fonte(20) if mobile else fonte(28),
            weight=ft.FontWeight.BOLD,
            color=TEXTO_PRIMARIO,
        ),
    ]
    if subtitulo and (not mobile or subtitulo_no_celular):
        # No celular o subtítulo descritivo é omitido (a barra superior já dá
        # o contexto); telas que trazem informação real nele — como o Início —
        # pedem exibição com subtitulo_no_celular=True.
        controles.append(
            ft.Text(
                subtitulo,
                size=fonte(12) if mobile else fonte(14),
                color=TEXTO_SECUNDARIO,
                max_lines=3,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )
    return ft.Column(controles, spacing=4)


def criar_painel_informativo(
    titulo: str, mensagem: str, icone=ft.Icons.INFO_OUTLINE
) -> ft.Container:
    """Painel de destaque com o mesmo estilo do Dashboard."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(icone, color=COR_DESTAQUE, size=fonte(22)),
                        ft.Text(
                            titulo, size=fonte(16), weight=ft.FontWeight.W_600,
                            color=TEXTO_PRIMARIO,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Text(mensagem, size=fonte(14), color=TEXTO_SECUNDARIO),
            ],
            spacing=8,
        ),
        padding=24,
        bgcolor=FUNDO_ELEVADO,
        border=ft.Border.all(1, BORDA_SUAVE),
        border_radius=14,
        shadow=_sombra_card(0.25),
    )


# ---------------------------------------------------------------------------
# Layout adaptativo (PC x celular)
# ---------------------------------------------------------------------------


def _largura_dialog(page: ft.Page, largura_desktop: int) -> int:
    """Largura do conteúdo de um dialog/cartão, adaptada ao celular.

    No desktop devolve a largura desejada. No celular, limita à largura útil
    da tela (descontando as margens do próprio dialog) para o conteúdo não ser
    espremido a ponto de o texto quebrar letra a letra.
    """
    if not eh_mobile():
        return largura_desktop
    if page is not None and page.width:
        return max(240, min(largura_desktop, int(page.width) - 64))
    return min(largura_desktop, 320)


def linha_campos(*campos, spacing: int = 12) -> ft.Control:
    """Campos de formulário lado a lado no PC; empilhados no celular."""
    if eh_mobile():
        return ft.Column(
            list(campos), spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    return ft.Row(list(campos), spacing=spacing)


def abrir_url(page: ft.Page, url: str) -> None:
    """Abre a URL no navegador do sistema (PC e celular).

    No celular é preciso ``page.launch_url``, que é assíncrona: chamada sem
    ``await`` nada acontece (em silêncio). E ela **não pode ir direto** para o
    ``page.run_task``, que exige uma função corrotina de verdade — como o Flet
    a embrulha num decorador de descontinuação, ``inspect.iscoroutinefunction``
    devolve False e o run_task levanta TypeError. Por isso envolvemos numa
    corrotina nossa, que satisfaz as duas exigências.
    """
    if eh_mobile():

        async def _abrir() -> None:
            await page.launch_url(url)

        page.run_task(_abrir)
    else:
        webbrowser.open(url)


def _rotulo_entrega() -> str:
    """Texto do botão de entrega do arquivo conforme a plataforma."""
    return "Salvar arquivo" if eh_mobile() else "Abrir pasta"


def _icone_entrega():
    return ft.Icons.SAVE_ALT if eh_mobile() else ft.Icons.FOLDER_OPEN


# ---------------------------------------------------------------------------
# Avisos e progresso
# ---------------------------------------------------------------------------


def mostrar_aviso(page: ft.Page, titulo: str, mensagem: str) -> None:
    """Exibe um dialog informativo."""
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo),
            content=ft.Text(mensagem),
            actions=[ft.TextButton("OK", on_click=lambda _: page.pop_dialog())],
        )
    )


def mostrar_sucesso(page: ft.Page, mensagem: str) -> None:
    """Confirmação discreta no rodapé (snackbar), sem interromper o fluxo."""
    page.show_dialog(
        ft.SnackBar(
            content=ft.Text(mensagem, color="#04342C", weight=ft.FontWeight.W_600),
            bgcolor=COR_DESTAQUE_CLARA,
        )
    )


def executar_com_progresso(page: ft.Page, mensagem: str, tarefa: Callable[[], object]):
    """Mostra um anel de progresso enquanto roda ``tarefa`` e devolve o resultado.

    A geração de PDF/PNG é síncrona e pode demorar. Como a interface do Flet roda
    num cliente separado, o anel continua animando durante o processamento — dando
    ao usuário o retorno visual de que algo está acontecendo. Envolve apenas a
    tarefa pesada; os avisos de sucesso/erro vêm depois, no chamador.
    """
    dialogo = ft.AlertDialog(
        modal=True,
        content=ft.Row(
            [
                ft.ProgressRing(width=22, height=22, stroke_width=3),
                ft.Text(mensagem),
            ],
            spacing=16,
            tight=True,
        ),
    )
    page.show_dialog(dialogo)
    page.update()
    try:
        return tarefa()
    finally:
        page.pop_dialog()
        page.update()
