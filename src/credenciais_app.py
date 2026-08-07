"""Credenciais OAuth do aplicativo (preenchidas na compilação).

Ficam **vazias no repositório**: o GitHub Actions injeta os valores a partir
dos *secrets* na hora de gerar os instaladores. Assim quem usa o app não
precisa criar nada — é só "Entrar com Google" — e nada secreto vai para o
código publicado.

Basta **um** cliente, do tipo "App para computador": PC e celular usam o mesmo
fluxo (navegador + retorno em 127.0.0.1). As chaves DISPOSITIVO existiam para o
fluxo de dispositivo (código digitado), abandonado porque o Google recusa o
escopo ``drive.appdata`` nele; ficam aqui só para não quebrar compilações
antigas e podem ser removidas no futuro.

Quem compila do código-fonte pode deixar tudo vazio e informar as próprias
credenciais em Ajustes → Backup na nuvem → Usar minhas credenciais.
"""

from __future__ import annotations

CLIENT_ID_DESKTOP = ""
CLIENT_SECRET_DESKTOP = ""

# Obsoletas (fluxo de dispositivo abandonado) — ver docstring acima.
CLIENT_ID_DISPOSITIVO = ""
CLIENT_SECRET_DISPOSITIVO = ""
