"""Regras de negócio puras — sem dependência de Flet nem do banco.

Separadas de ``main.py`` para permitir testes automatizados (ver
``tests/test_servicos.py``). As funções aqui recebem os dados já carregados e
devolvem decisões; quem persiste no banco é o ``main.py``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Container


def _chave_data_br(data_str: str) -> tuple[str, str, str]:
    """Chave ordenável (ano, mês, dia) a partir de uma data DD/MM/AAAA."""
    return (data_str[6:10], data_str[3:5], data_str[0:2])


def escolher_rodizio_presidentes(
    ordem_ids: list[int],
    datas_alvo: list[str],
    especiais: Container[str],
    designacoes_existentes: dict[str, int],
) -> list[tuple[str, int]]:
    """Decide, por rodízio justo, quem preside cada data ainda vazia.

    Para cada data alvo sem presidente, escolhe quem presidiu há mais tempo (ou
    nunca), desempatando pela ordem do cadastro (rodízio). Assim respeita a
    sequência inicial quando está tudo vazio, mas se adapta a mudanças manuais.
    Pula datas especiais e as que já têm alguém designado.

    Args:
        ordem_ids: ids dos presidentes na ordem do rodízio (cadastro).
        datas_alvo: datas DD/MM/AAAA das semanas do mês, em ordem cronológica.
        especiais: datas DD/MM/AAAA a pular (feriados/eventos).
        designacoes_existentes: histórico completo {data DD/MM/AAAA: presidente_id}.

    Returns:
        Lista ``[(data_str, presidente_id)]`` só para as datas efetivamente
        preenchidas, na ordem de ``datas_alvo``.
    """
    if not ordem_ids or not datas_alvo:
        return []

    ordem_pos = {pid: indice for indice, pid in enumerate(ordem_ids)}
    designacoes = {
        _chave_data_br(data_str): pid
        for data_str, pid in designacoes_existentes.items()
    }

    escolhas: list[tuple[str, int]] = []
    for data_str in datas_alvo:
        chave = _chave_data_br(data_str)
        if data_str in especiais or chave in designacoes:
            continue

        # Última vez que cada candidato presidiu antes desta data.
        ultima: dict[int, tuple] = {}
        for k, pid in designacoes.items():
            if k < chave and pid in ordem_pos and k > ultima.get(pid, ()):
                ultima[pid] = k

        # Quem presidiu há mais tempo (ou nunca); desempate pela ordem do rodízio.
        escolhido = min(
            ordem_ids, key=lambda pid: (ultima.get(pid, ()), ordem_pos[pid])
        )
        escolhas.append((data_str, escolhido))
        designacoes[chave] = escolhido

    return escolhas


def oradores_mais_tempo_sem_discurso(
    orador_ids: list[int],
    ultima_data_por_orador: dict[int, str],
) -> list[int]:
    """Ordena oradores do que está há mais tempo sem discursar para o mais recente.

    Quem nunca discursou vem primeiro. Em caso de empate, mantém a ordem de
    ``orador_ids`` (que o chamador passa já ordenada, ex.: alfabética).

    Args:
        orador_ids: ids dos oradores candidatos, na ordem de desempate.
        ultima_data_por_orador: {orador_id: última data DD/MM/AAAA que discursou}.
            Um id ausente significa que nunca discursou.

    Returns:
        Os mesmos ids, reordenados (há mais tempo sem discursar primeiro).
    """

    def chave(orador_id: int) -> tuple[str, str, str]:
        data = ultima_data_por_orador.get(orador_id)
        # "" ordena antes de qualquer ano real, então "nunca" vem primeiro.
        return _chave_data_br(data) if data else ("", "", "")

    # sorted é estável: empates preservam a ordem original de orador_ids.
    return sorted(orador_ids, key=chave)


def weekdays_sugeridos(
    tipo: str,
    weekday_minha: int | None,
    weekday_host: int | None,
    weekday_padrao: int | None = None,
) -> list[tuple[int, str]]:
    """Dias da semana que fazem sentido sugerir, conforme quem ouve o discurso.

    - ``recebido``: o orador vem falar **na minha congregação** → só os dias da
      **minha** reunião. Sugerir o dia da outra congregação seria marcar um
      discurso num dia em que não temos reunião.
    - ``enviado``: nosso orador vai falar **na outra congregação** → só os dias
      da reunião **dela**.

    Se o dia da congregação que importa não estiver cadastrado, cai no padrão
    observado nas designações do mês (melhor do que não sugerir nada).

    Returns:
        ``[(weekday, origem)]`` com origem em ``{"minha", "host", "padrao"}``.
    """
    principal = weekday_minha if tipo == "recebido" else weekday_host
    origem = "minha" if tipo == "recebido" else "host"
    if principal is not None:
        return [(principal, origem)]
    if weekday_padrao is not None:
        return [(weekday_padrao, "padrao")]
    return []


def sugerir_recebidos(
    oradores: list[dict],
    prioritarios: set[int],
    ultimo_uso_por_tema: dict[int, str],
    limite: int = 12,
    max_por_orador: int = 3,
) -> list[dict]:
    """Ranqueia pares orador+tema para receber da congregação anfitriã.

    A ordem privilegia: 1) temas marcados como PRIORITÁRIOS para a minha
    congregação; 2) temas nunca feitos ou há mais tempo sem uso; 3) o número
    do tema (desempate estável). Um orador aparece no máximo ``max_por_orador``
    vezes, para a lista não ser dominada por quem faz muitos temas.

    Args:
        oradores: [{id, nome, temas: [nr, ...], qualquer_tema: bool}] — os
            oradores disponíveis da anfitriã com os temas que podem fazer.
        prioritarios: números dos temas prioritários.
        ultimo_uso_por_tema: {nr: chave ordenável 'AAAAMM...'} — '' ou ausente
            significa que o tema nunca foi feito.
        limite: máximo de sugestões retornadas.
        max_por_orador: máximo de sugestões por orador.

    Returns:
        [{orador_id, orador_nome, tema_nr, prioritario, nunca_feito,
          ultimo_uso_chave}] em ordem de recomendação.
    """
    todos_os_temas = sorted(ultimo_uso_por_tema.keys())
    pares: list[tuple] = []
    for orador in oradores:
        temas = (
            todos_os_temas
            if orador.get("qualquer_tema")
            else sorted(set(orador.get("temas") or []))
        )
        for nr in temas:
            chave_uso = ultimo_uso_por_tema.get(nr, "") or ""
            eh_prioritario = nr in prioritarios
            pares.append(
                (
                    (0 if eh_prioritario else 1, chave_uso, nr),
                    {
                        "orador_id": orador["id"],
                        "orador_nome": orador.get("nome", ""),
                        "tema_nr": nr,
                        "prioritario": eh_prioritario,
                        "nunca_feito": not chave_uso,
                        "ultimo_uso_chave": chave_uso,
                    },
                )
            )

    pares.sort(key=lambda item: item[0])
    sugestoes: list[dict] = []
    usos_por_orador: dict[int, int] = {}
    for _chave, sugestao in pares:
        oid = sugestao["orador_id"]
        if usos_por_orador.get(oid, 0) >= max_por_orador:
            continue
        usos_por_orador[oid] = usos_por_orador.get(oid, 0) + 1
        sugestoes.append(sugestao)
        if len(sugestoes) >= limite:
            break
    return sugestoes


def montar_mensagem_presidencia(
    cantico: str,
    orador: str,
    congregacao: str,
    tema: str,
) -> str:
    """Mensagem que o coordenador manda ao presidente da reunião do dia.

    Formato combinado com o usuário — uma linha por informação, sem enfeites,
    para o presidente copiar direto no anúncio:

        Cântico: 34 - Andarei em integridade (Salmo 26)
        Orador: Carlos Menezes
        Congregação: Jardim Maria Sampaio
        Tema: Ande no caminho da integridade

    Campos vazios viram ``—`` para o presidente perceber o que ainda falta.
    """
    campos = (
        ("Cântico", cantico),
        ("Orador", orador),
        ("Congregação", congregacao),
        ("Tema", tema),
    )
    return "\n".join(
        f"{rotulo}: {(valor or '').strip() or '—'}" for rotulo, valor in campos
    )


def detectar_conflitos_oradores(registros: list[dict]) -> list[dict]:
    """Detecta oradores designados mais de uma vez na mesma data.

    Args:
        registros: dicts com ``data`` (DD/MM/AAAA), ``orador_id`` e, opcional,
            ``orador_nome``.

    Returns:
        Um dict por conflito: ``{data, orador_id, orador_nome, ocorrencias}``,
        ordenado por data e por orador.
    """
    por_chave: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for registro in registros:
        orador_id = registro.get("orador_id")
        data = registro.get("data")
        if orador_id is None or not data:
            continue
        por_chave[(data, orador_id)].append(registro)

    conflitos = [
        {
            "data": data,
            "orador_id": orador_id,
            "orador_nome": lista[0].get("orador_nome", ""),
            "ocorrencias": len(lista),
        }
        for (data, orador_id), lista in por_chave.items()
        if len(lista) > 1
    ]
    conflitos.sort(key=lambda c: (_chave_data_br(c["data"]), c["orador_id"]))
    return conflitos
