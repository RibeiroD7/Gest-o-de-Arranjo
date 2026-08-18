"""src/tabela.py — o substituto do pandas.

Trocar pandas por código próprio economizou ~27 MB no APK, mas passou a ser
NOSSA a responsabilidade por detalhes que a biblioteca resolvia sozinha:
nulo virando texto, ordenação com valores ausentes, ano de planilha chegando
como float. É o que estes testes fixam.
"""

import sqlite3

import pytest

from tabela import Coluna, Mascara, Tabela, filtrar


@pytest.fixture
def tab():
    return Tabela(
        [
            {"id": 1, "nome": "Ana", "n": 3},
            {"id": 2, "nome": "Bruno", "n": 1},
            {"id": 3, "nome": None, "n": 2},
        ],
        ["id", "nome", "n"],
    )


class TestLeitura:
    def test_de_consulta_traz_colunas_na_ordem_do_select(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE t (a INTEGER, b TEXT)")
        conn.execute("INSERT INTO t VALUES (1, 'x')")
        tabela = Tabela.de_consulta(conn, "SELECT b, a FROM t")
        assert tabela.colunas == ["b", "a"]
        assert tabela.iloc[0] == {"b": "x", "a": 1}

    def test_de_consulta_aceita_parametros(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE t (a INTEGER)")
        conn.executemany("INSERT INTO t VALUES (?)", [(1,), (2,)])
        assert len(Tabela.de_consulta(conn, "SELECT a FROM t WHERE a = ?", (2,))) == 1

    def test_empty_e_len(self, tab):
        assert not tab.empty and len(tab) == 3
        assert Tabela([], ["a"]).empty

    def test_itertuples_por_atributo_e_por_tupla(self, tab):
        assert [li.nome for li in tab.itertuples()] == ["Ana", "Bruno", None]
        assert list(tab.itertuples(index=False, name=None))[0] == (1, "Ana", 3)

    def test_itertuples_cai_para_tupla_com_coluna_nao_identificadora(self):
        """As colunas de ano dos temas ("2025") não são nomes Python válidos."""
        tabela = Tabela([{"2025": "x", "nr": 1}], ["2025", "nr"])
        assert list(tabela.itertuples()) == [("x", 1)]

    def test_iterar_devolve_dicionarios(self, tab):
        assert [li["nome"] for li in tab] == ["Ana", "Bruno", None]


class TestFiltrarEComparar:
    def test_comparacao_vira_mascara(self, tab):
        assert list(tab["nome"] == "Ana") == [True, False, False]
        assert list(tab["nome"] != "Ana") == [False, True, True]

    def test_mascara_filtra_a_tabela(self, tab):
        assert tab[tab["n"] == 2].to_dict() == [{"id": 3, "nome": None, "n": 2}]

    def test_mascara_combina_e_conta(self, tab):
        assert ((tab["n"] == 1) | (tab["n"] == 2)).sum() == 2
        assert ((tab["n"] == 1) & (tab["n"] == 2)).sum() == 0
        assert (~(tab["n"] == 1)).sum() == 2

    def test_filtrar_ignora_maiusculas_e_nulos(self, tab):
        assert len(filtrar(tab, "BRU", ["nome"])) == 1
        assert len(filtrar(tab, "zzz", ["nome"])) == 0

    def test_filtrar_sem_termo_devolve_copia(self, tab):
        copia = filtrar(tab, "  ", ["nome"])
        assert len(copia) == 3
        copia.linhas[0]["nome"] = "Trocado"
        assert tab.iloc[0]["nome"] == "Ana", "a cópia não pode alterar o original"

    def test_filtrar_por_coluna_inexistente_nao_quebra(self, tab):
        assert len(filtrar(tab, "ana", ["coluna_que_nao_existe"])) == 0

    def test_filtrar_busca_em_varias_colunas(self, tab):
        assert len(filtrar(tab, "3", ["id", "n"])) == 2  # id=3 e n=3

    def test_nao_comeca_com(self):
        tabela = Tabela([{"t": "(Não use)"}, {"t": "Normal"}, {"t": None}], ["t"])
        assert list(tabela["t"].nao_comeca_com("(")) == [False, True, True]


class TestOrdenar:
    def test_por_uma_coluna_nos_dois_sentidos(self, tab):
        assert [li["n"] for li in tab.sort_values("n")] == [1, 2, 3]
        assert [li["n"] for li in tab.sort_values("n", ascending=False)] == [3, 2, 1]

    def test_nulo_vem_primeiro_sem_estourar(self, tab):
        assert [li["nome"] for li in tab.sort_values("nome")] == [None, "Ana", "Bruno"]

    def test_varias_colunas_a_primeira_predomina(self):
        tabela = Tabela(
            [
                {"g": "b", "n": 1},
                {"g": "a", "n": 2},
                {"g": "a", "n": 1},
            ],
            ["g", "n"],
        )
        ordenada = tabela.sort_values(["g", "n"])
        assert [(li["g"], li["n"]) for li in ordenada] == [("a", 1), ("a", 2), ("b", 1)]

    def test_ascending_por_coluna(self):
        tabela = Tabela([{"g": "a", "n": 1}, {"g": "a", "n": 2}], ["g", "n"])
        ordenada = tabela.sort_values(["g", "n"], ascending=[True, False])
        assert [li["n"] for li in ordenada] == [2, 1]

    def test_ordenar_nao_altera_o_original(self, tab):
        tab.sort_values("n")
        assert [li["n"] for li in tab] == [3, 1, 2]


class TestColuna:
    def test_astype_str_transforma_nulo_em_vazio(self, tab):
        assert list(tab["nome"].astype(str)) == ["Ana", "Bruno", ""]

    def test_dropna_e_unique(self):
        coluna = Coluna([1, None, 1, 2])
        assert coluna.dropna().unique() == [1, 2]

    def test_iloc_por_posicao(self, tab):
        assert tab["nome"].iloc[0] == "Ana"

    def test_coluna_inexistente_vira_nulos(self, tab):
        assert list(tab["nao_existe"]) == [None, None, None]


class TestDefinir:
    def test_grava_so_nas_linhas_marcadas(self, tab):
        tab.definir(tab["id"] == 2, "nome", "Trocado")
        assert [li["nome"] for li in tab] == ["Ana", "Trocado", None]


class TestPlanilha:
    def test_inteiro_como_float_vira_int(self):
        """O calamine devolve o ano do cabeçalho como 2024.0; int("2024.0") falha."""
        from tabela import _normalizar_celula

        assert _normalizar_celula(2024.0) == 2024
        assert isinstance(_normalizar_celula(2024.0), int)
        assert _normalizar_celula(1.5) == 1.5
        assert _normalizar_celula("texto") == "texto"
        assert _normalizar_celula(None) is None

    def test_grade_fora_do_intervalo_devolve_nulo(self):
        from tabela import Grade

        grade = Grade([[1, 2], [3]])
        assert grade.iloc[0, 1] == 2
        assert grade.iloc[1, 1] is None, "linha curta não pode estourar"
        assert grade.iloc[99, 0] is None
        assert grade.shape == (2, 2)

    def test_le_aba_com_cabecalho(self, tmp_path):
        from openpyxl import Workbook

        from tabela import ler_aba_com_cabecalho

        caminho = tmp_path / "p.xlsx"
        wb = Workbook()
        aba = wb.active
        aba.title = "Dados"
        aba.append(["Nome*", "Telefone"])
        aba.append(["Ana", 11999])
        aba.append(["Bruno", None])
        wb.save(caminho)

        linhas = ler_aba_com_cabecalho(caminho, "Dados")
        assert linhas == [
            {"Nome*": "Ana", "Telefone": "11999"},
            {"Nome*": "Bruno", "Telefone": None},
        ]
        assert ler_aba_com_cabecalho(caminho, "Inexistente") is None


def test_mascara_isolada():
    assert Mascara([1, 0, 1]).sum() == 2
