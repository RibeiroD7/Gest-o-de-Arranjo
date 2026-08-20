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
        "minha_congregacao": lambda: main.tela_minha_congregacao(page, lambda: None),
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
        assert main.tela_minha_congregacao(page, lambda: None) is not None
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
def test_falar_com_o_responsavel_da_anfitria(mobile, monkeypatch):
    """Contato do responsável pela congregação do mês, no diálogo do mês."""
    import armazenamento

    armazenamento.definir_layout_mobile(mobile)
    try:
        page = _page()
        arranjo = {"id": 1, "ano": 2026, "mes_inicio": 10, "congregacao_host_id": 7}

        # Com telefone: monta a mensagem e oferece WhatsApp.
        monkeypatch.setattr(
            main, "carregar_congregacao",
            lambda _id: {
                "nome": "Jardim Bela Vista",
                "responsavel": "Paulo Souza",
                "telefone": "11977776666",
            },
        )
        main.abrir_dialog_falar_responsavel(page, arranjo)

        # Sem telefone cadastrado: avisa em vez de abrir um WhatsApp vazio.
        avisos = []
        monkeypatch.setattr(
            main, "carregar_congregacao",
            lambda _id: {"nome": "Jardim Bela Vista", "responsavel": "", "telefone": ""},
        )
        monkeypatch.setattr(
            main, "mostrar_aviso",
            lambda page, titulo, msg: avisos.append(titulo),
        )
        main.abrir_dialog_falar_responsavel(page, arranjo)
        assert avisos == ["Sem telefone cadastrado"]

        # O rodapé só mostra o botão quando há para quem ligar.
        nada = lambda *a, **k: None  # noqa: E731
        assert main._criar_rodape_dialog_mes(nada, nada, nada, nada) is not None
        assert main._criar_rodape_dialog_mes(nada, nada, nada) is not None
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
def test_escolher_contato_constroi_com_e_sem_agenda(mobile):
    """O seletor precisa abrir mesmo antes de qualquer .vcf ter sido lido."""
    import armazenamento
    from contatos import Contato

    armazenamento.definir_layout_mobile(mobile)
    try:
        page = _page()
        main._contatos_da_sessao.clear()
        main.abrir_dialog_escolher_contato(page, lambda c: None)

        main._contatos_da_sessao.append(Contato("Fábio Moreira", ["11999998888"]))
        main.abrir_dialog_escolher_contato(page, lambda c: None)

        # O botão preenche o telefone (e o nome, se estiver vazio).
        campo_tel = flet.TextField()
        campo_nome = flet.TextField()
        botao = main._botao_buscar_contato(page, campo_tel, campo_nome)
        assert botao is not None
    finally:
        main._contatos_da_sessao.clear()
        armazenamento.definir_layout_mobile(False)


@pytest.mark.parametrize("mobile", [False, True])
def test_conversar_so_aparece_com_telefone(mobile):
    """Botão de WhatsApp na lista de oradores: sem número não há para onde ir."""
    import armazenamento
    from tabela import Tabela

    armazenamento.definir_layout_mobile(mobile)
    try:
        colunas = ["id", "nome", "categoria", "telefone", "observacoes", "temas"]
        df = Tabela(
            [
                dict(zip(colunas, (1, "Com Telefone", "Ancião", "(11) 90000-0000", "", "1, 2"))),
                dict(zip(colunas, (2, "Sem Telefone", "Ancião", "", "", ""))),
            ],
            colunas,
        )
        nada = lambda *a, **k: None  # noqa: E731
        lista = main._criar_lista_oradores(df, {"ids": set()}, nada, nada, nada)

        chats = []

        def visitar(controle):
            if (
                isinstance(controle, flet.IconButton)
                and controle.icon == flet.Icons.CHAT_OUTLINED
            ):
                chats.append(controle)
            for attr in ("content", "controls"):
                filho = getattr(controle, attr, None)
                if isinstance(filho, list):
                    for f in filho:
                        visitar(f)
                elif filho is not None and not isinstance(filho, str):
                    visitar(filho)

        visitar(lista)
        assert len(chats) == 1, "só o orador com telefone deve ter o botão"
    finally:
        armazenamento.definir_layout_mobile(False)


@pytest.mark.parametrize("mobile", [False, True])
def test_presidentes_tem_campo_de_telefone_com_rotulo_e_botao_de_contato(mobile):
    """O botão de contatos sumiu uma vez, junto com o rótulo do campo.

    Ele tinha virado `suffix` do TextField — o campo parou de mostrar o rótulo
    "Telefone" e o ícone não aparecia. Agora fica ao lado, no diálogo de
    cadastro do presidente, e isto trava os dois.
    """
    import armazenamento

    armazenamento.definir_layout_mobile(mobile)
    try:
        page = _page()
        capturado = {}
        page.show_dialog = lambda dialog: capturado.setdefault("dialog", dialog)
        main.abrir_dialog_presidente(page, None, lambda: None)
        tela = capturado["dialog"]

        encontrados = {"campos": [], "contato": []}

        def visitar(controle):
            if isinstance(controle, flet.TextField):
                encontrados["campos"].append(controle.label)
            # No celular é IconButton; no PC, um TextButton com o mesmo ícone.
            if getattr(controle, "icon", None) == flet.Icons.CONTACT_PHONE_OUTLINED:
                encontrados["contato"].append(controle)
            for attr in ("content", "controls"):
                filho = getattr(controle, attr, None)
                if isinstance(filho, list):
                    for f in filho:
                        visitar(f)
                elif filho is not None and not isinstance(filho, str):
                    visitar(filho)

        visitar(tela)
        assert "Telefone" in encontrados["campos"]
        assert "Nome" in encontrados["campos"]
        assert encontrados["contato"], "botão de buscar contato sumiu"
    finally:
        armazenamento.definir_layout_mobile(False)


class TestBotaoBuscarContato:
    """No celular abre a agenda do sistema; no PC (sem a extensão), o .vcf."""

    def teardown_method(self):
        main._contatos_nativo_global = None

    def test_sem_extensao_cai_no_arquivo_vcf(self, monkeypatch):
        main._contatos_nativo_global = None
        abertos = []
        monkeypatch.setattr(
            main, "abrir_dialog_escolher_contato",
            lambda page, ao_escolher: abertos.append(ao_escolher),
        )
        page = _page()
        botao = main._botao_buscar_contato(page, flet.TextField(), flet.TextField())
        botao.on_click(None)
        assert abertos, "sem o seletor nativo o botão precisa abrir o .vcf"

    def test_com_extensao_usa_o_seletor_nativo(self, monkeypatch):
        import asyncio

        class ContatosFalso:
            async def escolher(self):
                return {
                    "id": "chave-lucas",
                    "nome": "Fábio Moreira",
                    "telefones": ["(11) 99999-8888"],
                    "foto": None,
                }

        main._contatos_nativo_global = ContatosFalso()
        monkeypatch.setattr(
            main, "abrir_dialog_escolher_contato",
            lambda *a, **k: pytest.fail("não deveria cair no .vcf"),
        )

        agendados = []
        page = _page()
        page.run_task = lambda handler, *args: agendados.append((handler, args))

        campo_tel, campo_nome = flet.TextField(), flet.TextField()
        vinculo = {"contato_id": ""}
        main._botao_buscar_contato(page, campo_tel, campo_nome, vinculo).on_click(None)

        assert agendados, "o seletor nativo precisa ir pelo run_task"
        handler, args = agendados[0]
        asyncio.run(handler(*args))
        # Telefone entra já com máscara e o nome preenche o campo vazio.
        assert campo_tel.value == "(11) 99999-8888"
        assert campo_nome.value == "Fábio Moreira"
        # A chave do contato é o que faz o telefone acompanhar a agenda depois.
        assert vinculo["contato_id"] == "chave-lucas"

    def test_cancelar_no_seletor_nao_abre_o_vcf(self, monkeypatch):
        """Cancelou de propósito: empurrar o outro caminho seria atrapalhar."""
        import asyncio

        class ContatosCancelado:
            async def escolher(self):
                return None

        main._contatos_nativo_global = ContatosCancelado()
        monkeypatch.setattr(
            main, "abrir_dialog_escolher_contato",
            lambda *a, **k: pytest.fail("cancelar não deve abrir o .vcf"),
        )
        agendados = []
        page = _page()
        page.run_task = lambda handler, *args: agendados.append((handler, args))
        campo = flet.TextField()
        main._botao_buscar_contato(page, campo).on_click(None)
        asyncio.run(agendados[0][0](*agendados[0][1]))
        assert not campo.value

    def test_falha_do_seletor_cai_no_vcf(self, monkeypatch):
        """Aparelho sem agenda ou plugin ausente: não pode ficar sem saída."""
        import asyncio

        class ContatosQuebrado:
            async def escolher(self):
                raise RuntimeError("MissingPluginException")

        main._contatos_nativo_global = ContatosQuebrado()
        abertos = []
        monkeypatch.setattr(
            main, "abrir_dialog_escolher_contato",
            lambda page, ao_escolher: abertos.append(ao_escolher),
        )
        agendados = []
        page = _page()
        page.run_task = lambda handler, *args: agendados.append((handler, args))
        main._botao_buscar_contato(page, flet.TextField()).on_click(None)
        asyncio.run(agendados[0][0](*agendados[0][1]))
        assert abertos, "falha no nativo precisa cair no .vcf"


@pytest.mark.parametrize("mobile", [False, True])
def test_relatorio_da_largura_para_a_coluna_de_nome(mobile):
    """A coluna do nome precisa de largura explícita, senão nasce com zero.

    Foi o que aconteceu com `expand=True`: dentro da coluna rolável a sobra é
    zero e os nomes sumiam do relatório, deixando só os números.
    """
    import armazenamento

    armazenamento.definir_layout_mobile(mobile)
    try:
        itens = [{"nome": "Rafael Pires", "valor": 8, "detalhe": "12/09/2026"}]
        largura = 315 if mobile else 680
        (tabela,) = main._lista_ranking_relatorio(itens, largura, "#14B8A6", "vazio")

        larguras = []

        def visitar(controle):
            if isinstance(controle, flet.Text) and controle.value == "Rafael Pires":
                larguras.append(controle.width)
            for attr in ("content", "controls"):
                filho = getattr(controle, attr, None)
                if isinstance(filho, list):
                    for f in filho:
                        visitar(f)
                elif filho is not None and not isinstance(filho, str):
                    visitar(filho)

        visitar(tabela)
        assert larguras and all(w and w > 60 for w in larguras), larguras
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


def test_row_com_wrap_nao_tem_filho_expand():
    """`wrap=True` numa Row com filho `expand=True` quebra o layout no Flet.

    A aba Presidentes virou um retângulo cinza vazio no celular por causa
    disso: o Flet não resolve a largura do filho elástico dentro de uma linha
    que quebra, e a seção inteira some. Como o estrago é visual (não levanta
    exceção, então construir a tela não pega), a checagem é no código-fonte.
    """
    import ast
    import pathlib

    def e_row(no):
        return (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "Row"
        )

    def tem_kw_true(no, nome):
        return any(
            kw.arg == nome
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in no.keywords
        )

    problemas = []
    for arquivo in sorted(pathlib.Path("src").glob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))

        # `x = ft.Column(..., expand=True)` — o filho elástico costuma ser
        # montado numa variável e só depois entrar na Row, então seguir o nome
        # é o que faz a checagem valer para o código como ele é escrito.
        elasticos = {
            alvo.id
            for no in ast.walk(arvore)
            if isinstance(no, ast.Assign) and isinstance(no.value, ast.Call)
            and tem_kw_true(no.value, "expand")
            for alvo in no.targets
            if isinstance(alvo, ast.Name)
        }

        def elastico(filho, elasticos=elasticos):
            if isinstance(filho, ast.Starred):
                filho = filho.value
            if isinstance(filho, ast.Call):
                return tem_kw_true(filho, "expand")
            return isinstance(filho, ast.Name) and filho.id in elasticos

        for no in ast.walk(arvore):
            if not (e_row(no) and tem_kw_true(no, "wrap")):
                continue
            # Só os filhos DIRETOS: expand num neto é problema de outro pai.
            filhos = no.args[0].elts if no.args and isinstance(no.args[0], ast.List) else []
            if any(elastico(f) for f in filhos):
                problemas.append(f"{arquivo.name}:{no.lineno}")

    assert not problemas, (
        "ft.Row com wrap=True e filho direto expand=True — a seção some da "
        "tela: " + ", ".join(problemas)
    )


def test_tela_oradores_no_filtro_outras_congregacoes():
    """O bloco "Outras congregações" agrupa por congregação e quebrou uma vez.

    A saída do pandas deixou um `groupby` sem substituto ali. Como o filtro
    começa em "Minha congregação", construir a tela não passava por esse
    caminho — só quem clicasse na outra aba via o erro. Aqui a tela é montada
    e o renderizador é chamado no modo "outras", que é onde estava o defeito.
    """
    import database

    conn = database.get_connection()
    try:
        database.create_tables(conn)
        conn.execute("DELETE FROM arranjo_oradores")
        conn.execute("DELETE FROM oradores")
        conn.execute("DELETE FROM congregacoes")
        conn.execute("INSERT INTO congregacoes (nome) VALUES ('Minha'), ('Vila'), ('Alfa')")
        ids = {n: i for i, n in conn.execute("SELECT id, nome FROM congregacoes")}
        conn.execute(
            "INSERT INTO oradores (nome, categoria, congregacao_id) "
            "VALUES ('Daqui', 'Ancião', ?), ('De Vila', 'Ancião', ?), ('De Alfa', 'Ancião', ?)",
            (ids["Minha"], ids["Vila"], ids["Alfa"]),
        )
        conn.commit()
    finally:
        conn.close()
    main.salvar_configuracao(
        {
            "nome_congregacao": "Minha", "endereco": "", "cidade": "", "cep": "",
            "coordenador_discursos": "", "telefone_coordenador": "",
            "dia_reuniao": "sábado", "horario_reuniao": "19:00", "circuito": "",
        }
    )

    capturado = {}
    original = main.criar_tela_padrao

    def espiao(**kwargs):
        capturado["render"] = kwargs["renderizador_tabela"]
        return original(**kwargs)

    main.criar_tela_padrao = espiao
    try:
        assert main.tela_oradores(_page(), lambda: None) is not None
    finally:
        main.criar_tela_padrao = original

    # É este o caminho que quebrava: agrupar as OUTRAS congregações.
    dados = main.filtrar_dataframe(
        main.carregar_dados(main.SQL_ORADORES), "", ["nome"]
    )
    outras = dados[dados["congregacao"] != "Minha"]
    assert len(outras) == 2
    assert capturado["render"](outras) is not None


@pytest.mark.parametrize("mobile", [False, True])
def test_presidentes_sao_linhas_num_quadro_so(mobile):
    """A aba Presidentes segue o formato da tela de Oradores.

    Eram cartões grandes e soltos: cabiam sete numa tela e reordenar o rodízio
    virava um rolar sem fim. O teste trava o formato — um quadro só, uma linha
    por presidente, e a última sem divisória embaixo.
    """
    import armazenamento
    import database

    conn = database.get_connection()
    try:
        database.create_tables(conn)
        conn.execute("DELETE FROM presidentes")
        conn.execute("DELETE FROM presidentes_cadastro")
        conn.commit()
    finally:
        conn.close()
    for nome in ("Primeiro", "Segundo", "Terceiro"):
        database.salvar_presidente_cadastro(nome, "Ancião", telefone="11999998888")

    armazenamento.definir_layout_mobile(mobile)
    try:
        secao = main._secao_presidentes(_page(), lambda: None)
        quadros = [c for c in secao.controls if isinstance(c, flet.Container)]
        assert quadros, "a lista deveria estar dentro de um container"
        linhas = quadros[-1].content.controls
        assert len(linhas) == 3, "uma linha por presidente, num quadro só"
        assert linhas[-1].border.bottom.width == 0, "a última linha não leva divisória"
        assert linhas[0].border.bottom.width == 1
    finally:
        armazenamento.definir_layout_mobile(False)
