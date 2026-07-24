"""Testes das regras de negócio puras (src/servicos.py)."""

from servicos import (
    _chave_data_br,
    detectar_conflitos_oradores,
    escolher_rodizio_presidentes,
    oradores_mais_tempo_sem_discurso,
)


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


class TestOradoresMaisTempoSemDiscurso:
    def test_nunca_discursou_vem_primeiro(self):
        # 20 nunca discursou; 10 discursou recente; 30 discursou há mais tempo.
        ultima = {10: "01/06/2026", 30: "01/02/2026"}
        ordem = oradores_mais_tempo_sem_discurso([10, 20, 30], ultima)
        assert ordem == [20, 30, 10]

    def test_ordena_por_data_crescente(self):
        ultima = {1: "10/03/2026", 2: "05/01/2026", 3: "20/12/2025"}
        assert oradores_mais_tempo_sem_discurso([1, 2, 3], ultima) == [3, 2, 1]

    def test_empate_mantem_ordem_de_entrada(self):
        # Dois nunca discursaram: preserva a ordem passada (ex.: alfabética).
        ordem = oradores_mais_tempo_sem_discurso([7, 4], {})
        assert ordem == [7, 4]

    def test_nao_muta_entrada(self):
        ids = [1, 2, 3]
        oradores_mais_tempo_sem_discurso(ids, {2: "01/01/2026"})
        assert ids == [1, 2, 3]


class TestDetectarConflitosOradores:
    def test_mesmo_orador_na_mesma_data(self):
        registros = [
            {"data": "04/01/2026", "orador_id": 1, "orador_nome": "Ana"},
            {"data": "04/01/2026", "orador_id": 1, "orador_nome": "Ana"},
            {"data": "11/01/2026", "orador_id": 1, "orador_nome": "Ana"},
        ]
        conflitos = detectar_conflitos_oradores(registros)
        assert conflitos == [
            {"data": "04/01/2026", "orador_id": 1, "orador_nome": "Ana", "ocorrencias": 2}
        ]

    def test_sem_conflitos(self):
        registros = [
            {"data": "04/01/2026", "orador_id": 1},
            {"data": "04/01/2026", "orador_id": 2},
            {"data": "11/01/2026", "orador_id": 1},
        ]
        assert detectar_conflitos_oradores(registros) == []

    def test_ignora_registros_incompletos(self):
        registros = [
            {"data": "04/01/2026", "orador_id": None},
            {"data": "", "orador_id": 1},
            {"orador_id": 1},
        ]
        assert detectar_conflitos_oradores(registros) == []
