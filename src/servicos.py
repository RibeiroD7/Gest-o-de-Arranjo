"""Regras de negócio puras — sem dependência de Flet nem do banco.

Separadas de ``main.py`` para permitir testes automatizados (ver
``tests/test_servicos.py``). As funções aqui recebem os dados já carregados e
devolvem decisões; quem persiste no banco é o ``main.py``.
"""

from __future__ import annotations

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
