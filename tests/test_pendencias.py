"""Prazo das pendências do Início: quando falha, não só quantas vezes.

"Falta 1 orador" para daqui a dez semanas e para daqui a nove dias apareciam
iguais na tela. O resumo do mês passa a devolver a primeira data descoberta,
que é de onde sai o prazo mostrado e a ordem da lista.
"""

from datetime import date

import pytest

flet = pytest.importorskip("flet")
flet.run = lambda *a, **k: None  # evita abrir a janela ao importar main

import database  # noqa: E402
import main  # noqa: E402


@pytest.fixture(autouse=True)
def _congregacao_com_reuniao_no_sabado():
    conn = database.get_connection()
    try:
        database.create_tables(conn)
    finally:
        conn.close()
    main.salvar_configuracao(
        {
            "nome_congregacao": "Minha", "endereco": "", "cidade": "", "cep": "",
            "coordenador_discursos": "", "telefone_coordenador": "",
            "dia_reuniao": "sábado", "horario_reuniao": "19:00", "circuito": "",
        }
    )


def _resumo(recebidos=None, presidentes=None):
    return main._resumo_mes_programacao(
        2026,
        9,
        recebidos=recebidos or {},
        presidentes=presidentes or {},
        contagens_ano={9: {"recebidos": 0, "enviados": 0}},
        especiais={},
    )


def test_primeira_semana_descoberta_e_a_primeira_do_mes():
    resumo = _resumo()
    # Setembro de 2026 começa numa terça; o primeiro sábado é dia 5.
    assert resumo["primeira_sem_orador"] == date(2026, 9, 5)
    assert resumo["primeira_sem_presidente"] == date(2026, 9, 5)


def test_semana_preenchida_empurra_o_prazo_para_a_seguinte():
    resumo = _resumo(recebidos={"05/09/2026": {"orador": "Alguém"}})
    assert resumo["primeira_sem_orador"] == date(2026, 9, 12)


def test_mes_inteiro_coberto_nao_tem_data_pendente():
    todas = {
        f"{dia:02d}/09/2026": {"orador": "Alguém"} for dia in (5, 12, 19, 26)
    }
    resumo = _resumo(recebidos=todas)
    assert resumo["primeira_sem_orador"] is None
    assert resumo["cobertas"] == resumo["semanas"]


def test_a_linha_da_pendencia_mostra_o_prazo():
    linha = main._linha_pendencia(date(2026, 9, 5), "Setembro: 1 semana sem orador", date(2026, 9, 1))
    textos = [c.value for c in linha.controls if isinstance(c, flet.Text)]
    assert "Setembro: 1 semana sem orador" in textos
    assert "em 4 dias" in textos


def test_pendencia_sem_data_nao_inventa_prazo():
    linha = main._linha_pendencia(None, "3 designação(ões) aguardando confirmação", date(2026, 9, 1))
    textos = [c.value for c in linha.controls if isinstance(c, flet.Text)]
    assert textos == ["3 designação(ões) aguardando confirmação"]
