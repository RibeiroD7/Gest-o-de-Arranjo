"""Fumaça de UI: constrói cada tela (e a linha de designação) sem abrir janela.

Fecha a lacuna que deixou passar o crash 'str' object has no attribute
'LARGURA_COL_DATA_MES' (o módulo `tema` era encoberto por uma variável local
`tema`): construir as telas e a linha da designação, em duas escalas de fonte,
pega esse tipo de regressão. Só roda onde o Flet estiver instalado.
"""

import types

import pytest

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # evita abrir a janela ao importar main

import main  # noqa: E402
import tema  # noqa: E402


def _page():
    return types.SimpleNamespace(
        update=lambda *a, **k: None,
        width=1200,
        window=types.SimpleNamespace(width=1200, height=800),
        show_dialog=lambda *a, **k: None,
        pop_dialog=lambda *a, **k: None,
        run_task=lambda *a, **k: None,
        platform=flet.PagePlatform.WINDOWS,
        on_keyboard_event=None,
        title="",
    )


def _telas(page, fp):
    return {
        "inicio": lambda: main.tela_inicio(page, lambda: None, lambda i: None),
        "programacao": lambda: main.tela_programacao(page, lambda: None, fp),
        "oradores": lambda: main.tela_oradores(page, lambda: None),
        "congregacoes": lambda: main.tela_congregacoes(page, lambda: None),
        "temas": lambda: main.tela_temas(page, fp),
        "quadro": lambda: main.tela_quadro_anuncios(page, lambda: None),
        "calendario": lambda: main.tela_calendario(page, lambda: None),
        "ajustes": lambda: main.tela_ajustes(page, lambda: None, fp),
    }


@pytest.fixture(autouse=True)
def _escala_padrao():
    yield
    tema.definir_escala(1.0)


@pytest.mark.parametrize("escala", [1.0, 1.4])
def test_todas_as_telas_constroem(escala):
    tema.definir_escala(escala)
    page, fp = _page(), flet.FilePicker()
    for nome, construir in _telas(page, fp).items():
        assert construir() is not None, f"tela {nome} não construiu (escala {escala})"


@pytest.mark.parametrize("escala", [1.0, 1.4])
def test_linha_e_tabela_de_designacao(escala):
    """Caminho exato do crash do APK: usa as larguras escaladas de tema.*."""
    tema.definir_escala(escala)
    registro = {
        "id": 1,
        "tipo": "enviado",
        "orador_nome": "Fulano",
        "tema_titulo": "Você conhece bem a Deus?",
        "tema_nr": 1,
        "data": "05/09/2026",
        "status": "pendente",
    }
    nada = lambda *a, **k: None  # noqa: E731
    assert main._criar_cabecalho_tabela_oradores() is not None
    assert main._criar_linha_orador_arranjo(
        registro, nada, nada, on_status=nada, on_mover=nada, on_whatsapp=nada
    ) is not None
    itens = main._montar_tabela_secao(
        [registro], "vazio", nada, nada, on_status=nada, on_mover=nada
    )
    assert itens
