"""Configuração dos testes.

Redireciona o armazenamento (banco, backups, exports) para uma pasta temporária
ANTES de qualquer import de ``armazenamento``/``database``, isolando a suíte do
banco real em ``data/``. O ``armazenamento`` lê ``FLET_APP_STORAGE_DATA`` no
momento do import, então definimos a variável aqui, no topo do conftest, que o
pytest importa antes dos módulos de teste.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="ga-testes-"))
os.environ["FLET_APP_STORAGE_DATA"] = str(_TMP)

# Importar `main` executa `flet.run(...)`, que abriria a janela do app e
# travaria a suíte. Neutralizar aqui vale para qualquer arquivo de teste,
# inclusive quando ele é rodado sozinho.
try:
    import flet

    flet.run = lambda *a, **k: None
except ImportError:  # sem flet instalado, os testes que precisam dele são pulados
    pass
