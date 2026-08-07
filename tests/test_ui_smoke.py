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


@pytest.mark.parametrize("mobile", [False, True])
def test_dialogos_de_presidentes_constroem(mobile):
    """Os dois diálogos de presidente montam layouts diferentes por plataforma.

    O layout de celular já tinha nascido quebrado uma vez (campos espremidos a
    uma letra por linha), então construir os dois caminhos vira regressão.
    """
    import armazenamento

    armazenamento.definir_layout_mobile(mobile)
    try:
        page = _page()
        main.abrir_dialog_gerenciar_presidentes(page, lambda: None)
        main.abrir_dialog_mensagem_presidencia(
            page,
            "31/10/2026",
            {"id": 1, "nome": "Fábio Moreira", "telefone": "11999998888"},
            {
                "orador_nome": "Carlos Menezes",
                "congregacao_nome": "Jardim Maria Sampaio",
                "tema_titulo": "Ande no caminho da integridade",
                "tema_nr": 34,
            },
        )
        # Sem nada programado na data o diálogo ainda precisa abrir (com aviso).
        main.abrir_dialog_mensagem_presidencia(page, "31/10/2026", {"nome": "X"}, None)
    finally:
        armazenamento.definir_layout_mobile(False)


@pytest.mark.parametrize("mobile", [False, True])
def test_ajustes_oferece_concluir_login_pendente(mobile, monkeypatch):
    """O resgate do login do Drive precisa aparecer em Ajustes, não só no diálogo.

    Quando o Android congela o app, o navegador para em ERR_CONNECTION_REFUSED
    e o diálogo de espera se perde — sem esse cartão o usuário ficaria sem
    caminho para concluir com o código que ficou no endereço.
    """
    import armazenamento
    import nuvem_drive

    monkeypatch.setattr(nuvem_drive, "login_pendente_valido", lambda *a, **k: True)
    monkeypatch.setattr(nuvem_drive, "esta_conectado", lambda *a, **k: False)
    armazenamento.definir_layout_mobile(mobile)
    try:
        assert main.tela_ajustes(_page(), lambda: None, flet.FilePicker()) is not None
    finally:
        armazenamento.definir_layout_mobile(False)


class TestAbrirUrl:
    """page.launch_url é corrotina: precisa ir por run_task, senão não abre nada.

    Foi exatamente esse esquecimento que impediu o login do Google no Android.
    """

    def teardown_method(self):
        import armazenamento
        armazenamento.definir_layout_mobile(False)

    def test_no_celular_abre_pelo_run_task(self, monkeypatch):
        """Replica a validação real do Flet e executa a corrotina de verdade.

        O Flet exige `inspect.iscoroutinefunction(handler)` no run_task — e o
        `page.launch_url` reprova nesse teste (vem embrulhado num decorador),
        o que derrubava o app no Android com "handler must be a coroutine
        function". Um `run_task` falso que aceita qualquer coisa não pega isso.
        """
        import asyncio
        import inspect

        import armazenamento
        import ui_comuns

        armazenamento.definir_layout_mobile(True)
        monkeypatch.delenv("GA_FORCAR_MOBILE", raising=False)

        capturado, abertas = [], []

        def run_task_como_no_flet(handler, *args):
            if not inspect.iscoroutinefunction(handler):
                raise TypeError("handler must be a coroutine function")
            capturado.append((handler, args))

        async def launch_url_falso(url):
            abertas.append(url)

        page = types.SimpleNamespace(
            run_task=run_task_como_no_flet, launch_url=launch_url_falso
        )
        ui_comuns.abrir_url(page, "https://exemplo.com")

        assert capturado, "nada foi agendado no run_task"
        handler, args = capturado[0]
        asyncio.run(handler(*args))  # roda a corrotina como o Flet faria
        assert abertas == ["https://exemplo.com"]

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


def test_todos_os_run_task_recebem_corrotinas():
    """Varre o código: page.run_task só aceita função corrotina de verdade.

    O Flet valida com inspect.iscoroutinefunction e levanta TypeError. Já
    derrubou o app duas vezes no Android (com page.launch_url e com um lambda),
    então a checagem virou teste.
    """
    import pathlib
    import re

    problemas = []
    for arquivo in pathlib.Path("src").glob("*.py"):
        codigo = arquivo.read_text(encoding="utf-8")
        for achado in re.finditer(r"run_task\(\s*([^\s,)]+)", codigo):
            handler = achado.group(1)
            linha = codigo[: achado.start()].count("\n") + 1
            if handler.startswith("lambda"):
                problemas.append(f"{arquivo.name}:{linha} passa um lambda")
                continue
            nome = handler.split(".")[-1]
            if not re.search(rf"\basync def {re.escape(nome)}\b", codigo):
                problemas.append(f"{arquivo.name}:{linha} passa {handler!r} (não é async def)")
    assert not problemas, "run_task com handler inválido:\n" + "\n".join(problemas)
