"""Preencher presidente sem afetar o rodízio: só a semana vazia daquele mês.

Cenário real: um ancião ou servo ministerial sai da congregação e a semana
dele fica sem presidente (o card do mês mostra "Falta: 1 sem presidente").
`preencher_presidentes_rodizio` — por trás do botão "Preencher em rodízio" na
aba Presidentes do mês, em Programação — precisa completar só essa lacuna,
com quem está há mais tempo sem presidir, sem tocar nas semanas que já têm
presidente, nos outros meses, nem no cadastro em Minha congregação →
Presidentes.
"""

import types

import pytest

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # evita abrir a janela ao importar main

import database  # noqa: E402
import main  # noqa: E402


def _preparar():
    conn = database.get_connection()
    try:
        database.create_tables(conn)
        conn.execute("DELETE FROM datas_especiais")
        conn.execute("DELETE FROM presidentes")
        conn.execute("DELETE FROM presidentes_cadastro")
        conn.commit()
    finally:
        conn.close()
    # Sábado fixo, sem depender do que outro teste deixou configurado.
    main.salvar_configuracao(
        {
            "nome_congregacao": "Teste",
            "endereco": "",
            "cidade": "",
            "cep": "",
            "coordenador_discursos": "",
            "telefone_coordenador": "",
            "dia_reuniao": "sábado",
            "horario_reuniao": "19:00",
            "circuito": "",
        }
    )


def _cadastrar(nomes):
    return {nome: database.salvar_presidente_cadastro(nome, "Ancião") for nome in nomes}


def _datas_do_mes(ano, mes):
    return [main._formatar_data_arranjo(d) for d in main._semanas_reuniao_mes(ano, mes)]


def test_preenche_so_a_semana_vazia_sem_mexer_nas_outras():
    _preparar()
    ids = _cadastrar(["Lucas", "Paulo", "Eduardo"])
    datas = _datas_do_mes(2026, 1)
    assert len(datas) >= 3, "o mês de teste precisa de pelo menos 3 sábados"

    # Todas as semanas preenchidas, alternando entre dois irmãos — só a 2ª
    # fica vazia, como quando alguém sai e a designação dele some.
    for indice, data_str in enumerate(datas):
        if indice == 1:
            continue
        database.salvar_presidente(data_str, ids["Lucas"] if indice % 2 == 0 else ids["Paulo"])

    preenchidas = main.preencher_presidentes_rodizio(2026, 1)

    assert preenchidas == 1
    presidentes_do_mes = database.carregar_presidentes_por_ano(2026)
    for indice, data_str in enumerate(datas):
        if indice == 1:
            continue
        esperado = ids["Lucas"] if indice % 2 == 0 else ids["Paulo"]
        assert presidentes_do_mes[data_str]["presidente_id"] == esperado
    assert datas[1] in presidentes_do_mes  # a vaga foi preenchida


def test_escolhe_quem_esta_a_mais_tempo_sem_presidir():
    _preparar()
    ids = _cadastrar(["Lucas", "Paulo", "Eduardo"])
    datas = _datas_do_mes(2026, 3)
    assert len(datas) >= 2

    # Lucas acabou de presidir na semana anterior à vaga.
    database.salvar_presidente(datas[0], ids["Lucas"])

    main.preencher_presidentes_rodizio(2026, 3)

    escolhido = database.carregar_presidentes_por_ano(2026)[datas[1]]["presidente_id"]
    assert escolhido != ids["Lucas"], "não pode repetir quem presidiu na semana anterior"


def test_nao_mexe_em_outro_mes():
    _preparar()
    ids = _cadastrar(["Lucas", "Paulo"])
    datas_dez = _datas_do_mes(2026, 12)
    datas_jan = _datas_do_mes(2027, 1)
    database.salvar_presidente(datas_dez[0], ids["Lucas"])

    main.preencher_presidentes_rodizio(2027, 1)

    presidentes_dez = database.carregar_presidentes_por_ano(2026)
    assert presidentes_dez[datas_dez[0]]["presidente_id"] == ids["Lucas"]
    assert len(presidentes_dez) == 1, "preencher janeiro não pode mexer em dezembro"
    assert datas_jan  # sanidade: o mês de teste existe


def test_nao_mexe_no_cadastro_de_presidentes():
    _preparar()
    ids = _cadastrar(["Lucas", "Paulo", "Eduardo"])
    antes = database.listar_presidentes_cadastro()

    main.preencher_presidentes_rodizio(2026, 4)

    depois = database.listar_presidentes_cadastro()
    assert depois == antes, "preencher a lacuna do mês não altera a aba Presidentes"
    assert set(ids.values()) == {item["id"] for item in depois}


class TestPresidenteAvulso:
    """Nome digitado à mão: tapa a semana sem entrar no revezamento.

    Cenário: o irmão que presidia 10/01 saiu da congregação. O coordenador
    quer que o nome dele continue aparecendo naquela data (a programação foi
    essa), mas isso não pode contar como presidência para o rodízio — ele não
    está mais na escala, e ninguém do cadastro deve "pagar" por essa semana.
    """

    def test_ocupa_a_data_e_o_rodizio_nao_preenche_por_cima(self):
        _preparar()
        _cadastrar(["Lucas", "Paulo", "Eduardo"])
        datas = _datas_do_mes(2026, 1)
        database.salvar_presidente_avulso(datas[1], "Otávio Vilela")

        main.preencher_presidentes_rodizio(2026, 1)

        do_ano = database.carregar_presidentes_por_ano(2026)
        assert do_ano[datas[1]]["nome"] == "Otávio Vilela"
        assert do_ano[datas[1]]["avulso"] is True
        assert do_ano[datas[1]]["presidente_id"] is None

    def test_nao_conta_como_presidencia_de_ninguem(self):
        _preparar()
        _cadastrar(["Lucas", "Paulo"])
        datas = _datas_do_mes(2026, 5)
        database.salvar_presidente_avulso(datas[0], "Otávio Vilela")

        relatorio = {item["nome"]: item["quantidade"] for item in database.relatorio_presidencias()}
        assert relatorio == {"Lucas": 0, "Paulo": 0}
        assert "Otávio Vilela" not in relatorio

    def test_nao_desequilibra_o_rodizio_dos_meses_seguintes(self):
        """A semana avulsa não pode fazer o rodízio pular ninguém."""
        _preparar()
        ids = _cadastrar(["Lucas", "Paulo"])
        datas = _datas_do_mes(2026, 6)
        database.salvar_presidente_avulso(datas[0], "Visitante")

        main.preencher_presidentes_rodizio(2026, 6)

        do_ano = database.carregar_presidentes_por_ano(2026)
        # A 1ª semana continua com o avulso; as demais foram para o cadastro.
        assert do_ano[datas[0]]["nome"] == "Visitante"
        designados = [
            do_ano[d]["presidente_id"] for d in datas[1:] if d in do_ano
        ]
        assert set(designados) <= set(ids.values())
        assert designados, "o rodízio precisa ter preenchido as outras semanas"

    def test_trocar_por_alguem_do_cadastro_limpa_o_nome_avulso(self):
        _preparar()
        ids = _cadastrar(["Lucas"])
        datas = _datas_do_mes(2026, 7)
        database.salvar_presidente_avulso(datas[0], "Otávio Vilela")

        database.salvar_presidente(datas[0], ids["Lucas"])

        registro = database.carregar_presidentes_por_ano(2026)[datas[0]]
        assert registro["nome"] == "Lucas"
        assert registro["avulso"] is False
        assert registro["presidente_id"] == ids["Lucas"]

    def test_trocar_de_alguem_do_cadastro_para_avulso(self):
        _preparar()
        ids = _cadastrar(["Lucas"])
        datas = _datas_do_mes(2026, 8)
        database.salvar_presidente(datas[0], ids["Lucas"])

        database.salvar_presidente_avulso(datas[0], "Otávio Vilela")

        registro = database.carregar_presidentes_por_ano(2026)[datas[0]]
        assert registro["nome"] == "Otávio Vilela"
        assert registro["avulso"] is True
        # Lucas deixa de ter aquela presidência no relatório.
        relatorio = {i["nome"]: i["quantidade"] for i in database.relatorio_presidencias()}
        assert relatorio["Lucas"] == 0

    def test_nome_vazio_e_recusado(self):
        _preparar()
        datas = _datas_do_mes(2026, 9)
        with pytest.raises(ValueError):
            database.salvar_presidente_avulso(datas[0], "   ")

    def test_excluir_a_data_remove_o_avulso(self):
        _preparar()
        datas = _datas_do_mes(2026, 10)
        database.salvar_presidente_avulso(datas[0], "Otávio Vilela")

        database.excluir_presidente(datas[0])

        assert datas[0] not in database.carregar_presidentes_por_ano(2026)


class TestTelaDoMesComAvulso:
    """O diálogo do mês precisa construir com um presidente avulso na lista.

    A linha de cada data monta um Dropdown; com um nome avulso ele ganha uma
    opção própria (o nome não está no cadastro). Construir o diálogo inteiro
    pega erro de montagem — inclusive o de closure tardia, em que todas as
    datas acabariam lendo a última iteração do laço.
    """

    def _arranjo(self):
        conn = database.get_connection()
        try:
            conn.execute("DELETE FROM arranjo_oradores")
            conn.execute("DELETE FROM arranjos")
            conn.execute(
                "INSERT INTO arranjos (ano, mes_inicio, mes_fim) VALUES (2026, 1, 1)"
            )
            conn.commit()
            return dict(
                zip(
                    ("id", "ano", "mes_inicio", "mes_fim"),
                    conn.execute(
                        "SELECT id, ano, mes_inicio, mes_fim FROM arranjos"
                    ).fetchone(),
                )
            )
        finally:
            conn.close()

    def test_o_dialogo_do_mes_constroi(self):
        import flet as ft

        _preparar()
        _cadastrar(["Lucas", "Paulo"])
        datas = _datas_do_mes(2026, 1)
        database.salvar_presidente_avulso(datas[1], "Otávio Vilela")
        arranjo = self._arranjo()

        dialogos = []
        page = types.SimpleNamespace(
            update=lambda *a, **k: None,
            width=1200,
            window=types.SimpleNamespace(width=1200, height=800),
            show_dialog=lambda d: dialogos.append(d),
            pop_dialog=lambda *a, **k: None,
            run_task=lambda *a, **k: None,
            platform=ft.PagePlatform.WINDOWS,
            on_keyboard_event=None,
            title="",
        )

        main.abrir_dialog_oradores_mes(
            page, arranjo, lambda i: None, lambda i: None, ft.FilePicker()
        )

        assert dialogos, "o diálogo do mês não foi construído"

    def test_o_dialogo_de_nome_avulso_constroi(self):
        import flet as ft

        _preparar()
        dialogos = []
        page = types.SimpleNamespace(
            update=lambda *a, **k: None,
            width=1200,
            window=types.SimpleNamespace(width=1200, height=800),
            show_dialog=lambda d: dialogos.append(d),
            pop_dialog=lambda *a, **k: None,
            run_task=lambda *a, **k: None,
            platform=ft.PagePlatform.WINDOWS,
            on_keyboard_event=None,
            title="",
        )

        main.abrir_dialog_presidente_avulso(page, "10/01/2026", lambda: None)

        assert dialogos, "o diálogo de nome avulso não foi construído"
