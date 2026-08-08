"""Fumaça de UI: constrói cada tela (e a linha de designação) sem abrir janela.

Fecha a lacuna que deixou passar o crash 'str' object has no attribute
'LARGURA_COL_DATA_MES' (o módulo `tema` era encoberto por uma variável local
`tema`): construir as telas e a linha da designação, em duas escalas de fonte,
pega esse tipo de regressão. Só roda onde o Flet estiver instalado.
"""

import types
from datetime import date

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
        "relatorios": lambda: main.tela_relatorios(page, lambda: None),
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
            orador="Carlos Menezes",
            congregacao="Jardim Maria Sampaio",
            tema="Ande no caminho da integridade",
        )
        # Sem nada programado na data o diálogo ainda precisa abrir (com aviso).
        main.abrir_dialog_mensagem_presidencia(page, "31/10/2026", {"nome": "X"})
    finally:
        armazenamento.definir_layout_mobile(False)


@pytest.mark.parametrize("mobile", [False, True])
def test_semana_de_data_especial_nao_pede_presidente(mobile):
    """Assembleia/congresso substituem a reunião: a linha mostra o evento.

    Sem isso a aba Presidentes exibia um seletor vazio na semana da assembleia,
    como se faltasse alguém — e o rodízio, que pula datas especiais, nunca ia
    preenchê-lo.
    """
    import armazenamento

    armazenamento.definir_layout_mobile(mobile)
    try:
        especial = {
            "id": 7,
            "data": "24/01/2026",
            "tipo": "Assembleia",
            "presidente_nome": "",
        }
        linha = main._linha_presidente_data_especial(
            _page(), 2026, 1, "Sábado, 24/01", especial, None, lambda: None
        )
        assert linha is not None
        # Presidente que sobrou de antes de a data virar especial: dá para tirar.
        com_sobra = main._linha_presidente_data_especial(
            _page(), 2026, 1, "Sábado, 24/01", especial,
            {"nome": "Gustavo Prado"}, lambda: None,
        )
        assert com_sobra is not None
    finally:
        armazenamento.definir_layout_mobile(False)


@pytest.mark.parametrize("mobile", [False, True])
def test_tela_inicial_manda_a_mensagem_da_presidencia(mobile):
    """O botão da mensagem mora na tela inicial (saiu da aba Presidentes).

    Só aparece com presidente definido: sem ele não há para quem mandar.
    """
    import armazenamento

    armazenamento.definir_layout_mobile(mobile)
    try:
        data_ref = date(2026, 1, 31)
        recebidos = {
            "31/01/2026": {
                "orador": "Carlos Menezes",
                "tema_nr": 34,
                "tema": "Ande no caminho da integridade",
                "congregacao": "Jardim Maria Sampaio",
            }
        }
        presidentes = {
            "31/01/2026": {"nome": "Bruno Vidal", "telefone": "11999998888"}
        }
        chamadas = []
        for com_presidente in (presidentes, {}):
            assert main._linha_agenda_inicio(
                data_ref, recebidos, com_presidente, {}, chamadas.append
            ) is not None
            assert main._card_proxima_reuniao(
                data_ref, recebidos, com_presidente, {}, chamadas.append
            ) is not None
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


def test_nenhum_uso_de_atributo_que_a_page_nao_tem():
    """Varre o código: tudo que se chama em `page.` precisa existir no Flet.

    O `page.set_clipboard()` sumiu no Flet 0.86 e derrubou o app inteiro no
    Android — e passou pelos testes porque só é chamado dentro de um handler,
    que a fumaça de UI não dispara. Uma varredura estática pega a próxima
    remoção de API antes de virar release.
    """
    import pathlib
    import re

    conhecidos = set(dir(flet.Page)) | set(flet.Page.__dataclass_fields__)
    problemas = []
    for arquivo in pathlib.Path("src").glob("*.py"):
        codigo = arquivo.read_text(encoding="utf-8")
        for achado in re.finditer(r"\bpage\.(\w+)", codigo):
            nome = achado.group(1)
            if nome not in conhecidos:
                linha = codigo[: achado.start()].count("\n") + 1
                problemas.append(f"{arquivo.name}:{linha} usa page.{nome}")
    assert not problemas, "atributo inexistente em ft.Page:\n" + "\n".join(problemas)


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
