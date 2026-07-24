"""Testes do rodízio justo de presidentes (src/servicos.py)."""

from servicos import _chave_data_br, escolher_rodizio_presidentes


class TestChaveDataBr:
    def test_ordenavel_por_ano_mes_dia(self):
        assert _chave_data_br("05/03/2026") == ("2026", "03", "05")
        # A ordenação lexicográfica corresponde à cronológica.
        assert _chave_data_br("04/01/2026") < _chave_data_br("11/01/2026")
        assert _chave_data_br("31/12/2025") < _chave_data_br("01/01/2026")


class TestEscolherRodizioPresidentes:
    def test_sem_cadastro_ou_sem_datas(self):
        assert escolher_rodizio_presidentes([], ["04/01/2026"], set(), {}) == []
        assert escolher_rodizio_presidentes([10, 20], [], set(), {}) == []

    def test_tudo_vazio_segue_ordem_do_cadastro(self):
        datas = ["04/01/2026", "11/01/2026", "18/01/2026"]
        escolhas = escolher_rodizio_presidentes([10, 20, 30], datas, set(), {})
        assert escolhas == [("04/01/2026", 10), ("11/01/2026", 20), ("18/01/2026", 30)]

    def test_rotaciona_apos_todos_presidirem(self):
        # 4 datas, 3 presidentes: o 4º volta para quem presidiu há mais tempo.
        datas = ["04/01/2026", "11/01/2026", "18/01/2026", "25/01/2026"]
        escolhas = escolher_rodizio_presidentes([10, 20, 30], datas, set(), {})
        assert [pid for _, pid in escolhas] == [10, 20, 30, 10]

    def test_pula_datas_ja_designadas(self):
        # 04/01 já tem presidente (30) no histórico: não deve ser reatribuída,
        # e conta como uso recente de 30.
        datas = ["04/01/2026", "11/01/2026", "18/01/2026"]
        historico = {"04/01/2026": 30}
        escolhas = escolher_rodizio_presidentes([10, 20, 30], datas, set(), historico)
        # 04/01 não sai na lista; 11/01 e 18/01 vão para quem presidiu há mais
        # tempo (10 e 20, pois 30 é o mais recente).
        assert escolhas == [("11/01/2026", 10), ("18/01/2026", 20)]

    def test_pula_datas_especiais(self):
        datas = ["04/01/2026", "11/01/2026", "18/01/2026"]
        especiais = {"11/01/2026"}
        escolhas = escolher_rodizio_presidentes([10, 20, 30], datas, especiais, {})
        # 11/01 é especial: pulada. Como não foi designada, não entra no
        # histórico, então 18/01 segue a ordem após 04/01.
        assert escolhas == [("04/01/2026", 10), ("18/01/2026", 20)]

    def test_respeita_historico_de_outro_ano(self):
        # 30 presidiu no fim de 2025 (mais recente que "nunca"): entra por último.
        datas = ["04/01/2026", "11/01/2026", "18/01/2026"]
        historico = {"28/12/2025": 30}
        escolhas = escolher_rodizio_presidentes([10, 20, 30], datas, set(), historico)
        assert [pid for _, pid in escolhas] == [10, 20, 30]

    def test_nao_muta_entrada(self):
        historico = {"04/01/2026": 30}
        original = dict(historico)
        escolher_rodizio_presidentes([10, 20, 30], ["11/01/2026"], set(), historico)
        assert historico == original
