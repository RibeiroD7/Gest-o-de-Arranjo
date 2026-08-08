"""Serviço que abre o seletor de contatos do próprio aparelho.

O lado Dart (``src/flutter/flet_contatos``) responde ao método ``escolher``
chamando o ``flutter_contacts``: o sistema mostra a agenda, o usuário toca num
contato e o app recebe de volta o nome e os telefones dele.

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
            ``{"nome": str, "telefones": list[str]}`` do contato escolhido, ou
            ``None`` se o usuário cancelou ou negou a permissão.
        """
        return await self._invoke_method("escolher")
