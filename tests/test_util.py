"""Testes das funções puras de data e texto (src/util.py)."""

from datetime import date, datetime

from util import (
    FUSO_SAO_PAULO,
    _datas_por_weekday_no_mes,
    _dia_semana_para_weekday,
    _formatar_data_arranjo,
    _formatar_data_exibicao,
    _normalizar_data_arranjo,
    _normalizar_texto_busca,
    _parse_data_arranjo,
    _rotulo_weekday,
    _weekday_mais_usado,
    aviso_backup_antigo,
    descrever_ultimo_envio,
    espera_de_resposta,
    formatar_data_hora_sao_paulo,
    ha_versao_mais_nova,
    rotulo_de_prazo,
)


class TestFormatarDataExibicao:
    def test_data_completa(self):
        assert _formatar_data_exibicao("05/03/2026") == "05/03/2026"

    def test_data_curta_mantida(self):
        assert _formatar_data_exibicao("05/03") == "05/03"

    def test_vazio_vira_travessao(self):
        assert _formatar_data_exibicao("") == "—"
        assert _formatar_data_exibicao(None) == "—"


class TestDiaSemanaParaWeekday:
    def test_dias_conhecidos(self):
        assert _dia_semana_para_weekday("segunda-feira") == 0
        assert _dia_semana_para_weekday("Terça") == 1
        assert _dia_semana_para_weekday("QUARTA-FEIRA") == 2
        assert _dia_semana_para_weekday("domingo") == 6
        assert _dia_semana_para_weekday("sábado") == 5

    def test_sem_acento(self):
        assert _dia_semana_para_weekday("terca") == 1
        assert _dia_semana_para_weekday("sabado") == 5

    def test_desconhecido_retorna_none(self):
        assert _dia_semana_para_weekday("feriado") is None
        assert _dia_semana_para_weekday("") is None


class TestNormalizarTextoBusca:
    def test_remove_acentos_e_caixa(self):
        assert _normalizar_texto_busca("João MARÍA") == "joao maria"

    def test_colapsa_espacos(self):
        assert _normalizar_texto_busca("  a   b  ") == "a b"

    def test_vazio(self):
        assert _normalizar_texto_busca("") == ""
        assert _normalizar_texto_busca(None) == ""


class TestNormalizarDataArranjo:
    def test_dia_mes_assume_2026(self):
        assert _normalizar_data_arranjo("5/3") == "05/03/2026"

    def test_data_completa_preserva_ano(self):
        assert _normalizar_data_arranjo("5.3.2025") == "05/03/2025"
        assert _normalizar_data_arranjo("05/03/2025") == "05/03/2025"

    def test_zero_padding(self):
        assert _normalizar_data_arranjo("1/2/2026") == "01/02/2026"

    def test_vazio_e_invalido(self):
        assert _normalizar_data_arranjo("") is None
        assert _normalizar_data_arranjo("abc") is None
        assert _normalizar_data_arranjo("1/2/3/4") is None


class TestParseDataArranjo:
    def test_valida(self):
        assert _parse_data_arranjo("05/03/2026") == date(2026, 3, 5)

    def test_dia_mes_usa_2026(self):
        assert _parse_data_arranjo("5/3") == date(2026, 3, 5)

    def test_invalida_retorna_none(self):
        assert _parse_data_arranjo("32/13/2026") is None
        assert _parse_data_arranjo("") is None
        assert _parse_data_arranjo(None) is None


class TestFormatarDataArranjo:
    def test_formato(self):
        assert _formatar_data_arranjo(date(2026, 3, 5)) == "05/03/2026"


class TestDatasPorWeekdayNoMes:
    def test_todas_no_mes_e_no_weekday(self):
        # Julho de 2026, quartas-feiras (weekday 2).
        datas = _datas_por_weekday_no_mes(2026, 7, 2)
        assert datas  # há pelo menos uma
        assert all(d.month == 7 and d.year == 2026 for d in datas)
        assert all(d.weekday() == 2 for d in datas)
        # Sequência crescente e espaçada de 7 em 7 dias.
        assert datas == sorted(datas)
        assert all((datas[i + 1] - datas[i]).days == 7 for i in range(len(datas) - 1))

    def test_fevereiro_domingos_2026(self):
        # Fevereiro de 2026 tem 4 domingos (weekday 6): 1, 8, 15, 22.
        datas = _datas_por_weekday_no_mes(2026, 2, 6)
        assert [d.day for d in datas] == [1, 8, 15, 22]


class TestWeekdayMaisUsado:
    def test_conta_por_tipo(self):
        registros = [
            {"tipo": "enviado", "data": "05/01/2026"},  # segunda (0)
            {"tipo": "enviado", "data": "12/01/2026"},  # segunda (0)
            {"tipo": "enviado", "data": "06/01/2026"},  # terça (1)
            {"tipo": "recebido", "data": "04/01/2026"},  # domingo — outro tipo
        ]
        assert _weekday_mais_usado(registros, "enviado") == 0

    def test_ignora_datas_invalidas_e_vazio(self):
        assert _weekday_mais_usado([], "enviado") is None
        assert _weekday_mais_usado([{"tipo": "enviado", "data": "xx"}], "enviado") is None


class TestRotuloWeekday:
    def test_nomes(self):
        assert _rotulo_weekday(0) == "Segunda-feira"
        assert _rotulo_weekday(5) == "Sábado"
        assert _rotulo_weekday(6) == "Domingo"


class TestHaVersaoMaisNova:
    def test_detecta_mais_nova(self):
        assert ha_versao_mais_nova("1.0.19", "1.0.18") is True
        assert ha_versao_mais_nova("1.1.0", "1.0.18") is True
        assert ha_versao_mais_nova("2.0.0", "1.9.9") is True

    def test_igual_ou_mais_velha(self):
        assert ha_versao_mais_nova("1.0.18", "1.0.18") is False
        assert ha_versao_mais_nova("1.0.17", "1.0.18") is False

    def test_aceita_prefixo_v_e_vazio(self):
        assert ha_versao_mais_nova("v1.0.19", "1.0.18") is True
        assert ha_versao_mais_nova("", "1.0.18") is False


class TestFormatarDataHoraSaoPaulo:
    """O Drive devolve a data em UTC; a tela mostra horário de Brasília."""

    def test_converte_de_utc_para_o_formato_brasileiro(self):
        assert formatar_data_hora_sao_paulo("2026-08-18T12:28:45.123Z") == "18/08/2026 09:28"

    def test_vira_o_dia_quando_passa_da_meia_noite_em_utc(self):
        assert formatar_data_hora_sao_paulo("2026-08-18T01:15:00Z") == "17/08/2026 22:15"

    def test_aceita_offset_explicito(self):
        assert formatar_data_hora_sao_paulo("2026-08-18T12:28:45+00:00") == "18/08/2026 09:28"

    def test_sem_data_ou_texto_estranho_nao_quebra(self):
        assert formatar_data_hora_sao_paulo(None) == "—"
        assert formatar_data_hora_sao_paulo("") == "—"
        assert formatar_data_hora_sao_paulo("qualquer coisa") == "qualquer coisa"


class TestAvisoBackupAntigo:
    """Restaurar um backup velho por cima de trabalho novo é perda silenciosa.

    Cenário real: a programação do mês é montada no computador e, dias depois,
    o celular oferece restaurar o backup da nuvem, que ainda é o de antes.
    """

    def test_backup_mais_velho_que_os_dados_avisa(self):
        aviso = aviso_backup_antigo(
            "2026-08-19T14:30:00", "2026-08-22T09:10:00", "Celular"
        )
        assert "19/08/2026" in aviso and "22/08/2026" in aviso
        assert "Celular" in aviso

    def test_backup_mais_novo_nao_avisa(self):
        assert aviso_backup_antigo("2026-08-22T09:10:00", "2026-08-19T14:30:00") == ""

    def test_diferenca_de_minutos_nao_avisa(self):
        # O banco é gravado por coisas que não são edição (escala de fonte,
        # backup do dia): poucos minutos não significam trabalho perdido.
        assert aviso_backup_antigo("2026-08-22T09:00:00", "2026-08-22T09:05:00") == ""

    def test_sem_aparelho_a_frase_nao_cita_origem(self):
        aviso = aviso_backup_antigo("2026-08-19T14:30:00", "2026-08-22T09:10:00")
        assert aviso and "gerado em" not in aviso

    def test_datas_ilegiveis_ou_ausentes_nao_avisam(self):
        assert aviso_backup_antigo("", "2026-08-22T09:10:00") == ""
        assert aviso_backup_antigo("2026-08-19T14:30:00", "") == ""
        assert aviso_backup_antigo("ontem", "2026-08-22T09:10:00") == ""

    def test_backup_da_nuvem_vem_em_utc(self):
        """O Drive devolve UTC com Z; o banco local guarda hora do aparelho."""
        # 12:00Z é 09:00 em São Paulo: o backup é anterior à alteração das 10h.
        assert aviso_backup_antigo("2026-08-22T12:00:00Z", "2026-08-22T10:00:00-03:00")


class TestRotuloDePrazo:
    """O prazo é o que separa "falta 1 orador" de "falta 1 orador para sábado"."""

    HOJE = date(2026, 9, 1)

    def test_sem_data_nao_tem_rotulo(self):
        assert rotulo_de_prazo(None, self.HOJE) == ("", "")

    def test_data_passada(self):
        assert rotulo_de_prazo(date(2026, 8, 29), self.HOJE) == ("já passou", "vencido")

    def test_hoje_e_amanha(self):
        assert rotulo_de_prazo(self.HOJE, self.HOJE) == ("é hoje", "urgente")
        assert rotulo_de_prazo(date(2026, 9, 2), self.HOJE) == ("é amanhã", "urgente")

    def test_dentro_da_semana_e_urgente(self):
        assert rotulo_de_prazo(date(2026, 9, 8), self.HOJE) == ("em 7 dias", "urgente")

    def test_ate_tres_semanas_pede_atencao(self):
        assert rotulo_de_prazo(date(2026, 9, 9), self.HOJE) == ("em 8 dias", "atencao")
        assert rotulo_de_prazo(date(2026, 9, 22), self.HOJE) == ("em 21 dias", "atencao")

    def test_mais_longe_conta_em_semanas(self):
        assert rotulo_de_prazo(date(2026, 9, 23), self.HOJE) == ("em 3 semanas", "tranquilo")
        assert rotulo_de_prazo(date(2026, 11, 30), self.HOJE) == ("em 12 semanas", "tranquilo")


class TestDescreverUltimoEnvio:
    """Um envio automático que parou de funcionar precisa aparecer na tela."""

    AGORA = datetime(2026, 9, 20, 10, 0, tzinfo=FUSO_SAO_PAULO)

    def test_nunca_enviou(self):
        texto, nivel = descrever_ultimo_envio("", self.AGORA)
        assert texto == "Nenhum backup enviado ainda."
        assert nivel == "atencao"

    def test_hoje_e_ontem(self):
        texto, nivel = descrever_ultimo_envio("2026-09-20T08:30:00-03:00", self.AGORA)
        assert texto.startswith("Último envio: hoje")
        assert nivel == ""
        texto, _ = descrever_ultimo_envio("2026-09-19T08:30:00-03:00", self.AGORA)
        assert texto.startswith("Último envio: ontem")

    def test_alguns_dias_mostra_a_contagem_e_a_data(self):
        texto, nivel = descrever_ultimo_envio("2026-09-15T08:30:00-03:00", self.AGORA)
        assert "há 5 dias" in texto and "15/09/2026" in texto
        assert nivel == ""

    def test_duas_semanas_paradas_chamam_atencao(self):
        _, nivel = descrever_ultimo_envio("2026-09-06T08:30:00-03:00", self.AGORA)
        assert nivel == "atencao"


class TestEsperaDeResposta:
    """Um convite de ontem e um de três semanas não podem ser a mesma linha."""

    HOJE = date(2026, 9, 20)

    def test_sem_convite_registrado_nao_inventa_espera(self):
        assert espera_de_resposta(None, self.HOJE) == ("", "")
        assert espera_de_resposta("", self.HOJE) == ("", "")

    def test_convite_de_hoje(self):
        texto, nivel = espera_de_resposta("2026-09-20T09:00:00", self.HOJE)
        assert texto == "convite enviado hoje"
        assert nivel == ""

    def test_um_dia_no_singular(self):
        assert espera_de_resposta("2026-09-19T09:00:00", self.HOJE)[0] == "1 dia sem resposta"

    def test_antes_do_prazo_nao_cobra(self):
        texto, nivel = espera_de_resposta("2026-09-17T09:00:00", self.HOJE)
        assert texto == "3 dias sem resposta"
        assert nivel == ""

    def test_passado_o_prazo_cobra(self):
        texto, nivel = espera_de_resposta("2026-09-15T09:00:00", self.HOJE)
        assert texto == "5 dias sem resposta"
        assert nivel == "atencao"
