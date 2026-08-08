"""Ponte com a agenda de contatos do próprio aparelho.

O lado Dart (``src/flutter/flet_contatos``) fala com o ``flutter_contacts``:
``escolher`` abre o seletor do sistema; ``reler`` busca de novo os contatos já
vinculados, para o app acompanhar o que mudar no aparelho.

Nada da agenda é lido sem o usuário escolher, e nada é guardado aqui — quem
decide o que salvar é o app.
"""

from typing import Optional

import flet as ft

__all__ = ["Contatos"]


@ft.control("Contatos")
class Contatos(ft.Service):
    """Seletor nativo de contatos (Android e iOS)."""

    async def escolher(self) -> Optional[dict]:
        """Abre a agenda do sistema e espera o usuário escolher.

        Returns:
            ``{"id": str, "nome": str, "telefones": list[str], "foto": str|None}``
            — ``foto`` em base64 — ou ``None`` se cancelou ou negou a permissão.
        """
        return await self._invoke_method("escolher")

    async def reler(self, ids: list[str]) -> list[dict]:
        """Relê os contatos vinculados, no mesmo formato de ``escolher``.

        Contatos apagados do aparelho simplesmente não voltam na lista — o app
        mantém o que já tinha, em vez de perder o telefone de alguém.
        """
        if not ids:
            return []
        return await self._invoke_method("reler", {"ids": list(ids)}) or []
