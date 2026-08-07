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


@pytest.fixture(scope="module", autouse=True)
def _banco_pronto():
    """As telas leem o banco: garante as tabelas mesmo rodando este arquivo só."""
    import database

    conn = database.get_connection()
    try:
        database.create_tables(conn)
    finally:
        conn.close()


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


class TestAbrirUrl:
    """page.launch_url é corrotina: precisa ir por run_task, senão não abre nada.

    Foi exatamente esse esquecimento que impediu o login do Google no Android.
    """

    def teardown_method(self):
        import armazenamento
        armazenamento.definir_layout_mobile(False)

    def test_no_celular_usa_run_task(self, monkeypatch):
        import armazenamento
        import ui_comuns

        armazenamento.definir_layout_mobile(True)
        monkeypatch.delenv("GA_FORCAR_MOBILE", raising=False)
        chamadas = []
        page = types.SimpleNamespace(
            run_task=lambda fn, *a: chamadas.append((fn, a)),
            launch_url="CORROTINA",
        )
        ui_comuns.abrir_url(page, "https://exemplo.com")
        assert chamadas == [("CORROTINA", ("https://exemplo.com",))]

    def test_no_pc_usa_o_navegador_do_sistema(self, monkeypatch):
        import armazenamento
        import ui_comuns

        armazenamento.definir_layout_mobile(False)
        monkeypatch.delenv("GA_FORCAR_MOBILE", raising=False)
        abertas = []
        monkeypatch.setattr(ui_comuns.webbrowser, "open", lambda u: abertas.append(u))
        page = types.SimpleNamespace(run_task=lambda *a, **k: pytest.fail("não usar run_task no PC"))
        ui_comuns.abrir_url(page, "https://exemplo.com")
        assert abertas == ["https://exemplo.com"]
