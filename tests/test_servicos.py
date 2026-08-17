"""Testes das regras de negócio puras (src/servicos.py)."""

from servicos import (
    _chave_data_br,
    detectar_conflitos_oradores,
    escolher_rodizio_presidentes,
    meses_de_atencao,
    oradores_mais_tempo_sem_discurso,
    sugerir_recebidos,
    weekdays_sugeridos,
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


class TestSugerirRecebidos:
    def _oradores(self):
        return [
            {"id": 1, "nome": "Ana", "temas": [10, 20], "qualquer_tema": False},
            {"id": 2, "nome": "Beto", "temas": [20, 30], "qualquer_tema": False},
        ]

    def test_prioritario_vem_primeiro(self):
        # Tema 30 é prioritário, mesmo tendo uso mais recente que o 10.
        uso = {10: "", 20: "202601", 30: "202606"}
        sugestoes = sugerir_recebidos(self._oradores(), {30}, uso)
        assert sugestoes[0]["tema_nr"] == 30
        assert sugestoes[0]["orador_id"] == 2
        assert sugestoes[0]["prioritario"] is True

    def test_nunca_feito_antes_de_usado(self):
        uso = {10: "", 20: "202601", 30: "202606"}
        sugestoes = sugerir_recebidos(self._oradores(), set(), uso)
        # 10 nunca feito (Ana) vem antes de 20 (jan) e 30 (jun).
        assert (sugestoes[0]["tema_nr"], sugestoes[0]["orador_id"]) == (10, 1)
        assert sugestoes[0]["nunca_feito"] is True
        assert [s["tema_nr"] for s in sugestoes[:2]] == [10, 20]

    def test_qualquer_tema_considera_todos(self):
        oradores = [{"id": 5, "nome": "Rafael", "temas": [], "qualquer_tema": True}]
        uso = {1: "", 2: "202601"}
        sugestoes = sugerir_recebidos(oradores, set(), uso)
        assert [s["tema_nr"] for s in sugestoes] == [1, 2]

    def test_limite_por_orador(self):
        oradores = [
            {"id": 1, "nome": "Ana", "temas": [1, 2, 3, 4, 5], "qualquer_tema": False},
            {"id": 2, "nome": "Beto", "temas": [6], "qualquer_tema": False},
        ]
        uso = {n: "" for n in range(1, 7)}
        sugestoes = sugerir_recebidos(oradores, set(), uso, max_por_orador=3)
        assert sum(1 for s in sugestoes if s["orador_id"] == 1) == 3
        assert any(s["orador_id"] == 2 for s in sugestoes)

    def test_limite_total(self):
        oradores = [
            {"id": 1, "nome": "Ana", "temas": list(range(1, 30)), "qualquer_tema": False}
        ]
        uso = {n: "" for n in range(1, 30)}
        assert len(sugerir_recebidos(oradores, set(), uso, limite=5, max_por_orador=99)) == 5


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

    def test_recebido_mais_enviado_e_o_mesmo_discurso(self):
        """Orador da própria congregação: um discurso, anotado dos dois lados.

        Ele entra como enviado (para receber a designação) e como recebido (na
        lista de quem discursa na semana). Acusar conflito aí só gera ruído —
        foi o que acontecia com todos os oradores locais.
        """
        registros = [
            {"data": "02/05/2026", "orador_id": 1, "orador_nome": "Danilo", "tipo": "recebido"},
            {"data": "02/05/2026", "orador_id": 1, "orador_nome": "Danilo", "tipo": "enviado"},
        ]
        assert detectar_conflitos_oradores(registros) == []

    def test_repeticao_no_mesmo_tipo_continua_sendo_conflito(self):
        """Dois compromissos do mesmo tipo no mesmo dia: aí é conflito de verdade."""
        registros = [
            {"data": "02/05/2026", "orador_id": 1, "orador_nome": "Danilo", "tipo": "enviado"},
            {"data": "02/05/2026", "orador_id": 1, "orador_nome": "Danilo", "tipo": "enviado"},
            {"data": "02/05/2026", "orador_id": 1, "orador_nome": "Danilo", "tipo": "recebido"},
        ]
        assert detectar_conflitos_oradores(registros) == [
            {"data": "02/05/2026", "orador_id": 1, "orador_nome": "Danilo", "ocorrencias": 2}
        ]


class TestWeekdaysSugeridos:
    """Quem ouve o discurso define as datas possíveis.

    Caso real: arranjo com Jardim Bela Vista (Domingo), minha congregação
    Jardim Aurora (Sábado). Ao RECEBER um orador, ele fala aqui — então só
    sábados. Antes o app sugeria também os domingos da outra congregação.
    """

    SABADO, DOMINGO = 5, 6

    def test_recebido_usa_so_os_meus_dias(self):
        assert weekdays_sugeridos("recebido", self.SABADO, self.DOMINGO) == [
            (self.SABADO, "minha")
        ]

    def test_enviado_usa_so_os_dias_da_outra(self):
        assert weekdays_sugeridos("enviado", self.SABADO, self.DOMINGO) == [
            (self.DOMINGO, "host")
        ]

    def test_cai_no_padrao_quando_falta_o_dia(self):
        # Minha congregação sem dia cadastrado: usa o padrão observado no mês.
        assert weekdays_sugeridos("recebido", None, self.DOMINGO, 2) == [(2, "padrao")]
        assert weekdays_sugeridos("enviado", self.SABADO, None, 3) == [(3, "padrao")]

    def test_sem_nada_nao_sugere(self):
        assert weekdays_sugeridos("recebido", None, None, None) == []

    def test_nunca_mistura_as_duas_congregacoes(self):
        for tipo in ("recebido", "enviado"):
            dias = [wd for wd, _ in weekdays_sugeridos(tipo, self.SABADO, self.DOMINGO, 1)]
            assert len(dias) == 1, f"{tipo} sugeriu mais de um dia da semana"


class TestMesesDeAtencao:
    """A janela que as Pendências do Início cobram.

    Cobrar o ano inteiro enchia a lista com meses que ainda nem tinham
    começado a ser montados — o arranjo se organiza com poucos meses de
    antecedência.
    """

    def test_inclui_o_mes_atual_e_os_dois_seguintes(self):
        assert meses_de_atencao(2026, 8) == [(2026, 8), (2026, 9), (2026, 10)]

    def test_vira_o_ano(self):
        assert meses_de_atencao(2026, 11) == [(2026, 11), (2026, 12), (2027, 1)]

    def test_dezembro(self):
        assert meses_de_atencao(2026, 12) == [(2026, 12), (2027, 1), (2027, 2)]

    def test_quantidade_configuravel(self):
        assert meses_de_atencao(2026, 8, 1) == [(2026, 8)]
        assert len(meses_de_atencao(2026, 8, 6)) == 6

    def test_quantidade_zero_ainda_cobra_o_mes_atual(self):
        """Nunca devolver lista vazia: sem o mês atual a tela não cobra nada."""
        assert meses_de_atencao(2026, 8, 0) == [(2026, 8)]


class TestRodizioOlhaParaOsDoisLados:
    """Designação futura também conta: olhar só para trás repetia gente.

    Caso real: o irmão preside o Discurso Especial do dia 26; ao refazer o
    rodízio do mês, ele era escolhido para o dia 12 — no dia 12 a designação
    do dia 26 ainda estava no futuro, então ele parecia livre.
    """

    def test_nao_escolhe_quem_ja_preside_semanas_depois(self):
        historico = {"26/09/2026": 10}  # Discurso Especial do dia 26
        escolhas = escolher_rodizio_presidentes(
            [10, 20, 30], ["05/09/2026", "12/09/2026"], {"26/09/2026"}, historico
        )
        assert dict(escolhas)["12/09/2026"] != 10, "não pode repetir 14 dias antes"
        assert 10 not in dict(escolhas).values()

    def test_quem_esta_mais_longe_da_propria_escala_vem_primeiro(self):
        # 20 preside no dia 05; 30 no dia 26. Para o dia 12, o mais distante
        # da própria escala é o 10 (nunca) e depois o 30 (14 dias).
        historico = {"05/09/2026": 20, "26/09/2026": 30}
        (escolha,) = escolher_rodizio_presidentes(
            [10, 20, 30], ["12/09/2026"], set(), historico
        )
        assert escolha == ("12/09/2026", 10)

    def test_com_todos_ocupados_escolhe_o_menos_apertado(self):
        """Sem folga para ninguém, vai para quem tem o intervalo maior."""
        historico = {"05/09/2026": 10, "26/09/2026": 20}
        (escolha,) = escolher_rodizio_presidentes(
            [10, 20], ["12/09/2026"], set(), historico
        )
        # 10 está a 7 dias; 20 a 14 — o 20 é o menos apertado.
        assert escolha == ("12/09/2026", 20)

    def test_data_invalida_no_historico_nao_quebra(self):
        historico = {"data ruim": 10, "26/09/2026": 20}
        escolhas = escolher_rodizio_presidentes(
            [10, 20], ["05/09/2026"], set(), historico
        )
        assert escolhas == [("05/09/2026", 10)]


class TestAlternanciaDePrivilegio:
    """Evita dois anciãos ou dois servos seguidos — sem atropelar o rodízio."""

    CATS = {10: "Ancião", 20: "Servo Ministerial", 30: "Ancião", 40: "Servo Ministerial"}

    def test_alterna_o_privilegio_semana_a_semana(self):
        datas = ["05/09/2026", "12/09/2026", "19/09/2026", "26/09/2026"]
        escolhas = escolher_rodizio_presidentes(
            [10, 20, 30, 40], datas, set(), {}, self.CATS
        )
        privilegios = [self.CATS[pid] for _, pid in escolhas]
        assert all(
            atual != seguinte
            for atual, seguinte in zip(privilegios, privilegios[1:])
        ), privilegios

    def test_sem_categorias_o_privilegio_nao_influencia(self):
        """Compatibilidade: quem não passa categorias mantém o comportamento."""
        datas = ["05/09/2026", "12/09/2026"]
        assert escolher_rodizio_presidentes([10, 20, 30, 40], datas, set(), {}) == [
            ("05/09/2026", 10),
            ("12/09/2026", 20),
        ]

    def test_alternancia_cede_quando_o_outro_privilegio_nao_tem_folga(self):
        """"A menos que não tenha outro jeito": o rodízio manda no aperto.

        Só há um ancião, e ele acabou de presidir. Alternar significaria
        chamá-lo de novo em uma semana — pior do que repetir o privilégio.
        """
        cats = {10: "Ancião", 20: "Servo Ministerial", 30: "Servo Ministerial"}
        historico = {"05/09/2026": 20, "12/09/2026": 10}
        (escolha,) = escolher_rodizio_presidentes(
            [10, 20, 30], ["19/09/2026"], set(), historico, cats
        )
        assert escolha[1] == 30, "deveria repetir o privilégio em vez de repetir a pessoa"

    def test_alternancia_nao_quebra_a_justica_entre_iguais(self):
        """Entre dois do privilégio certo, ainda vale quem está há mais tempo."""
        cats = {10: "Ancião", 20: "Servo Ministerial", 30: "Servo Ministerial"}
        # 20 presidiu recentemente; 30 nunca. O próximo servo deve ser o 30.
        historico = {"01/08/2026": 20, "05/09/2026": 10}
        (escolha,) = escolher_rodizio_presidentes(
            [10, 20, 30], ["12/09/2026"], set(), historico, cats
        )
        assert escolha[1] == 30


class TestTodosOsTemasDeUmOrador:
    """Escolhido um orador, a lista mostra os temas DELE em ordem.

    Antes o diálogo misturava a congregação inteira e mostrava no máximo três
    temas por pessoa — não dava para ver o que aquele irmão tem preparado.
    """

    def _um_orador(self):
        return [{"id": 1, "nome": "Danilo", "temas": list(range(1, 12)),
                 "qualquer_tema": False}]

    def test_traz_todos_os_temas_sem_o_limite_de_tres(self):
        uso = {n: "" for n in range(1, 12)}
        sugestoes = sugerir_recebidos(
            self._um_orador(), set(), uso, limite=300, max_por_orador=300
        )
        assert len(sugestoes) == 11

    def test_ordem_prioritario_nunca_feito_mais_antigo(self):
        uso = {1: "202610", 2: "", 3: "202501", 4: "202508"}
        oradores = [{"id": 1, "nome": "X", "temas": [1, 2, 3, 4],
                     "qualquer_tema": False}]
        ordem = [
            s["tema_nr"]
            for s in sugerir_recebidos(
                oradores, {4}, uso, limite=300, max_por_orador=300
            )
        ]
        # 4 é prioritário; depois o nunca feito (2); depois do mais antigo.
        assert ordem == [4, 2, 3, 1]
