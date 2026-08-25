"""Verificação de atualização: procura a versão publicada e traz o arquivo.

Duas portas: a verificação silenciosa da abertura, que só fala quando existe
versão nova, e o botão de Ajustes, que responde sempre. No computador o
instalador é baixado e aberto; no celular quem instala é o sistema, a partir
do APK que o navegador baixa, e o arquivo é escolhido pela arquitetura do
aparelho.
"""

from __future__ import annotations

import flet as ft

from armazenamento import eh_mobile
from log_app import logger
from tema import COR_DESTAQUE_CLARA, fonte
from ui_comuns import abrir_url, mostrar_aviso, mostrar_sucesso
from util import ha_versao_mais_nova
from versao import URL_API_RELEASE, URL_RELEASES, VERSAO_APP


def _url_instalador_plataforma(assets: list[dict]) -> str | None:
    """URL do arquivo da release para o sistema atual (Windows, Linux, Android)."""
    import sys

    if eh_mobile():
        # O APK sai por arquitetura: arm64 nos aparelhos atuais, armeabi-v7a
        # nos antigos de 32 bits. platform.machine() responde com a ABI do
        # Python empacotado dentro do próprio APK, que é a do aparelho.
        import platform

        maquina = (platform.machine() or "").lower()
        de_32_bits = "armv7" in maquina or maquina == "armv8l"
        sufixo = "-android-32bits.apk" if de_32_bits else "-android.apk"
    elif sys.platform.startswith("win"):
        sufixo = "-windows-instalador.exe"
    elif sys.platform.startswith("linux"):
        sufixo = "-linux.tar.gz"
    else:
        return None
    for asset in assets:
        if (asset.get("name") or "").endswith(sufixo):
            return asset.get("browser_download_url")
    return None


async def _baixar_e_abrir_instalador(page: ft.Page, url: str) -> None:
    """Baixa o instalador da nova versão e o abre para o usuário instalar."""
    import asyncio
    import os
    import sys
    import tempfile
    import urllib.request

    def _baixar() -> str:
        nome = url.rsplit("/", 1)[-1] or "GestaoArranjo-instalador"
        destino = os.path.join(tempfile.gettempdir(), nome)
        urllib.request.urlretrieve(url, destino)  # noqa: S310 — URL da release oficial
        return destino

    mostrar_sucesso(page, "Baixando atualização…")
    try:
        destino = await asyncio.to_thread(_baixar)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao baixar a atualização")
        mostrar_aviso(page, "Erro", "Não foi possível baixar a atualização.")
        return

    try:
        if sys.platform.startswith("win"):
            os.startfile(destino)  # noqa: S606 — instalador oficial baixado
        else:
            import subprocess

            subprocess.Popen(["xdg-open", destino])  # noqa: S603, S607
        mostrar_sucesso(page, "Instalador baixado. Siga a instalação para atualizar.")
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao abrir o instalador baixado")
        mostrar_aviso(
            page,
            "Instalador baixado",
            f"O arquivo está em {destino}. Abra-o para concluir a atualização.",
        )


def _buscar_release() -> dict:
    """Dados da última release publicada. Bloqueia: rodar fora da thread da UI."""
    import json
    import urllib.request

    requisicao = urllib.request.Request(
        URL_API_RELEASE, headers={"Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(requisicao, timeout=6) as resposta:  # noqa: S310
        return json.load(resposta)


def _baixar_atualizacao(page: ft.Page, url: str | None) -> None:
    """Leva o usuário à nova versão: instalador no PC, navegador no celular.

    No Android o aplicativo não instala a si mesmo — quem instala é o sistema,
    a partir do APK que o navegador baixa. Sem asset para esta plataforma,
    abre a página de releases.
    """
    if not url:
        abrir_url(page, URL_RELEASES)
    elif eh_mobile():
        # abrir_url, e não page.launch_url direto: no celular ela é assíncrona
        # e, chamada sem await, não faz nada — em silêncio. Era o botão
        # "Baixar" que não respondia no Android.
        abrir_url(page, url)
    else:
        # run_task exige uma função corrotina de verdade: um lambda (mesmo
        # devolvendo corrotina) é rejeitado com TypeError.
        page.run_task(_baixar_e_abrir_instalador, page, url)


def verificar_na_abertura(page: ft.Page) -> None:
    """Na abertura, avisa se saiu versão nova; em silêncio quando não saiu.

    A rede roda fora da thread da UI (``asyncio.to_thread``) e o aviso é exibido
    pelo laço do Flet — mesmo padrão de ``entregar_arquivo``. Erros (offline,
    timeout) são ignorados: quem abriu o app quer usá-lo, não ler falha de rede.
    O download só ocorre se o usuário clicar, e vem da release oficial.
    """

    async def _checar():
        import asyncio

        try:
            dados = await asyncio.to_thread(_buscar_release)
        except Exception:  # noqa: BLE001 — offline/erro de rede: só o log
            logger.debug("Não deu para verificar atualizações agora", exc_info=True)
            return
        tag = (dados.get("tag_name") or "").strip()
        if not ha_versao_mais_nova(tag, VERSAO_APP):
            return

        url_instalador = _url_instalador_plataforma(dados.get("assets") or [])
        page.show_dialog(
            ft.SnackBar(
                content=ft.Text(
                    f"Nova versão {tag.lstrip('v')} disponível.",
                    color="#04342C",
                    weight=ft.FontWeight.W_600,
                ),
                bgcolor=COR_DESTAQUE_CLARA,
                action="Baixar" if url_instalador else "Abrir",
                on_action=lambda _=None: _baixar_atualizacao(page, url_instalador),
                duration=10000,
            )
        )
        page.update()

    page.run_task(_checar)


def verificar_agora(page: ft.Page) -> None:
    """Procura atualização a pedido do usuário (botão em Ajustes).

    Ao contrário da verificação da abertura, esta sempre responde alguma coisa:
    o usuário clicou e precisa saber se está em dia, se saiu versão nova ou se
    a consulta falhou.
    """

    async def _checar():
        import asyncio

        try:
            dados = await asyncio.to_thread(_buscar_release)
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao procurar atualizações")
            mostrar_aviso(
                page,
                "Não foi possível verificar",
                "O GitHub não respondeu. Confira a conexão e tente de novo.",
            )
            return

        tag = (dados.get("tag_name") or "").strip()
        if not ha_versao_mais_nova(tag, VERSAO_APP):
            mostrar_aviso(
                page,
                "Aplicativo atualizado",
                f"A versão {VERSAO_APP} é a mais recente publicada.",
            )
            return

        url_instalador = _url_instalador_plataforma(dados.get("assets") or [])
        if eh_mobile():
            explicacao = (
                "O download abre no navegador. Ao terminar, toque no arquivo para "
                "instalar por cima desta versão. Os dados continuam onde estão."
            )
        else:
            explicacao = (
                "O instalador é baixado e aberto para você concluir a atualização."
            )

        def baixar(_=None):
            page.pop_dialog()
            _baixar_atualizacao(page, url_instalador)

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Versão {tag.lstrip('v')} disponível"),
                content=ft.Text(
                    f"Você está na {VERSAO_APP}.\n\n{explicacao}", size=fonte(13)
                ),
                actions=[
                    ft.TextButton("Agora não", on_click=lambda _: page.pop_dialog()),
                    ft.FilledButton(
                        "Baixar", icon=ft.Icons.DOWNLOAD, on_click=baixar
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    page.run_task(_checar)
