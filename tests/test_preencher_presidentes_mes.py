"""Preencher presidente sem afetar o rodízio: só a semana vazia daquele mês.

Cenário real: um ancião ou servo ministerial sai da congregação e a semana
dele fica sem presidente (o card do mês mostra "Falta: 1 sem presidente").
`preencher_presidentes_rodizio` — por trás do botão "Preencher em rodízio" na
aba Presidentes do mês, em Programação — precisa completar só essa lacuna,
com quem está há mais tempo sem presidir, sem tocar nas semanas que já têm
presidente, nos outros meses, nem no cadastro em Minha congregação →
Presidentes.
"""

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
