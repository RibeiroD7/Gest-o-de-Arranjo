"""Credenciais OAuth do aplicativo (preenchidas na compilação).

Ficam **vazias no repositório**: o GitHub Actions injeta os valores a partir
dos *secrets* na hora de gerar os instaladores. Assim quem usa o app não
precisa criar nada — é só "Entrar com Google" — e nada secreto vai para o
código publicado.

São dois clientes porque o Google exige tipos diferentes por fluxo:
- DESKTOP: cliente "App para computador" (login que volta sozinho ao app);
- DISPOSITIVO: cliente "TVs e dispositivos com entrada limitada" (Android,
  onde o usuário digita um código).

Quem compila do código-fonte pode deixar tudo vazio e informar as próprias
credenciais em Ajustes → Backup na nuvem → Usar minhas credenciais.
"""

from __future__ import annotations

CLIENT_ID_DESKTOP = ""
CLIENT_SECRET_DESKTOP = ""

CLIENT_ID_DISPOSITIVO = ""
CLIENT_SECRET_DISPOSITIVO = ""
