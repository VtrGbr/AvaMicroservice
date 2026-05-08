"""
Serviço de cálculo de oferta dos professores.

Regras:
- Aula vale R$ 30,00 base
- Cada criança presente acrescenta R$ 0,30
- Se há professor de apoio: valor dividido igualmente entre os dois
- Se o titular faltou: a metade do valor vai para o substituto
  (o titular não recebe nada por essa aula)
- Duas aulas por semana (dois horários disponíveis: manhã/tarde e noite)
"""

from models import db, Aula, Frequencia, Usuario
from sqlalchemy import extract


VALOR_BASE_AULA = 30.00
VALOR_POR_CRIANCA = 0.30


def calcular_valor_aula(aula: Aula) -> dict:
    """
    Retorna um dict com o valor bruto da aula e a distribuição entre professores.
    """
    presentes = aula.total_presentes
    valor_bruto = VALOR_BASE_AULA + (presentes * VALOR_POR_CRIANCA)

    distribuicao = {}

    tem_apoio = aula.professor_apoio_presente_id is not None

    if aula.titular_faltou:
        # Titular faltou: metade vai para o substituto
        # (a outra metade não é paga ao titular ausente)
        valor_substituto = valor_bruto / 2
        if aula.substituto_id:
            distribuicao[aula.substituto_id] = round(valor_substituto, 2)
        # Se havia apoio presente e titular faltou, o apoio recebe a outra metade
        if tem_apoio and aula.professor_apoio_presente_id:
            distribuicao[aula.professor_apoio_presente_id] = round(valor_bruto / 2, 2)
    else:
        if tem_apoio and aula.professor_apoio_presente_id:
            # Divide igualmente entre titular e apoio
            valor_cada = valor_bruto / 2
            distribuicao[aula.professor_responsavel_id] = round(valor_cada, 2)
            distribuicao[aula.professor_apoio_presente_id] = round(valor_cada, 2)
        else:
            # Titular sozinho
            distribuicao[aula.professor_responsavel_id] = round(valor_bruto, 2)

    return {
        'aula_id': aula.id,
        'data': aula.data.isoformat(),
        'horario': aula.horario,
        'turma': aula.turma.nome if aula.turma else '',
        'presentes': presentes,
        'valor_bruto': round(valor_bruto, 2),
        'titular_faltou': aula.titular_faltou,
        'distribuicao': distribuicao
    }


def calcular_oferta_mensal(mes: int, ano: int) -> list:
    """
    Retorna a oferta de cada professor no mês especificado.
    """
    aulas = Aula.query.filter(
        extract('month', Aula.data) == mes,
        extract('year', Aula.data) == ano
    ).all()

    totais = {}  # professor_id -> total_valor

    for aula in aulas:
        resultado = calcular_valor_aula(aula)
        for prof_id, valor in resultado['distribuicao'].items():
            totais[prof_id] = totais.get(prof_id, 0.0) + valor

    relatorio = []
    for prof_id, total in totais.items():
        prof = Usuario.query.get(prof_id)
        if prof:
            relatorio.append({
                'professor_id': prof_id,
                'professor_nome': prof.nome,
                'total_aulas': sum(
                    1 for a in aulas
                    if prof_id in calcular_valor_aula(a)['distribuicao']
                ),
                'valor_total': round(total, 2)
            })

    relatorio.sort(key=lambda x: x['professor_nome'])
    return relatorio


def detalhe_oferta_professor(professor_id: int, mes: int, ano: int) -> dict:
    """
    Retorna o detalhamento aula a aula de um professor no mês.
    """
    aulas = Aula.query.filter(
        extract('month', Aula.data) == mes,
        extract('year', Aula.data) == ano
    ).all()

    detalhes = []
    total = 0.0

    for aula in aulas:
        resultado = calcular_valor_aula(aula)
        if professor_id in resultado['distribuicao']:
            valor = resultado['distribuicao'][professor_id]
            total += valor
            detalhes.append({
                'data': resultado['data'],
                'horario': resultado['horario'],
                'turma': resultado['turma'],
                'presentes': resultado['presentes'],
                'valor_bruto_aula': resultado['valor_bruto'],
                'valor_recebido': valor,
                'titular_faltou': resultado['titular_faltou']
            })

    prof = Usuario.query.get(professor_id)
    return {
        'professor': prof.to_dict() if prof else None,
        'mes': mes,
        'ano': ano,
        'total_aulas': len(detalhes),
        'valor_total': round(total, 2),
        'detalhes': sorted(detalhes, key=lambda x: x['data'])
    }
