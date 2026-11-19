"""Lista Brasileira de Internações por Condições Sensíveis à Atenção Primária (ICSAP).

Baseada na Portaria SAS/MS nº 221, de 17 de abril de 2008, que define 19 grupos
de diagnósticos (CID-10). Conferida em 2026-11-19 com o texto publicado em
https://bvsms.saude.gov.br/bvs/saudelegis/sas/2008/prt0221_17_04_2008.html

No grupo 13 (diabetes), a portaria lista as subcategorias E10.0 a E14.9 uma a
uma; aqui elas aparecem como a faixa E10-E14, que cobre exatamente o mesmo.

Cada grupo é uma lista de faixas de códigos CID-10. Uma faixa como "A00-A09"
inclui todos os códigos de A00 a A09 (com qualquer subcategoria, ex.: A09.0).
Uma faixa com subcategoria, como "A15.0-A15.3", inclui só essas subcategorias.
"""

from __future__ import annotations

GRUPOS_ICSAP: dict[str, list[str]] = {
    "01 Doenças preveníveis por imunização e condições sensíveis": [
        "A33-A37", "A95", "B16", "B05-B06", "B26", "G00.0", "A17.0", "A19",
        "A15.0-A15.3", "A16.0-A16.2", "A15.4-A15.9", "A16.3-A16.9",
        "A17.1-A17.9", "A18", "I00-I02", "A51-A53", "B50-B54", "B77",
    ],
    "02 Gastroenterites infecciosas e complicações": ["E86", "A00-A09"],
    "03 Anemia": ["D50"],
    "04 Deficiências nutricionais": ["E40-E46", "E50-E64"],
    "05 Infecções de ouvido, nariz e garganta": ["H66", "J00-J03", "J06", "J31"],
    "06 Pneumonias bacterianas": ["J13-J14", "J15.3-J15.4", "J15.8-J15.9", "J18.1"],
    "07 Asma": ["J45-J46"],
    "08 Doenças pulmonares": ["J20-J21", "J40-J44", "J47"],
    "09 Hipertensão": ["I10-I11"],
    "10 Angina": ["I20"],
    "11 Insuficiência cardíaca": ["I50", "J81"],
    "12 Doenças cerebrovasculares": ["I63-I67", "I69", "G45-G46"],
    "13 Diabetes mellitus": ["E10-E14"],
    "14 Epilepsias": ["G40-G41"],
    "15 Infecção no rim e trato urinário": ["N10-N12", "N30", "N34", "N39.0"],
    "16 Infecção da pele e tecido subcutâneo": ["A46", "L01-L04", "L08"],
    "17 Doença inflamatória dos órgãos pélvicos femininos": ["N70-N73", "N75-N76"],
    "18 Úlcera gastrointestinal": ["K25-K28", "K92.0-K92.2"],
    "19 Doenças relacionadas ao pré-natal e parto": ["O23", "A50", "P35.0"],
}


def _normalizar(cid: str) -> str:
    """'J18.1', 'J181' e 'j181 ' viram 'J181'."""
    return str(cid).strip().upper().replace(".", "")


def _expandir_faixa(faixa: str) -> tuple[str, str]:
    """Converte uma faixa em limites (inicio, fim) comparáveis por prefixo."""
    inicio, _, fim = faixa.partition("-")
    return _normalizar(inicio), _normalizar(fim or inicio)


def _na_faixa(cid: str, inicio: str, fim: str) -> bool:
    # Compara só até o tamanho do limite: "A09" cobre "A090", "A099" etc.
    return inicio <= cid[: len(inicio)] and cid[: len(fim)] <= fim


_FAIXAS = [
    (grupo, *_expandir_faixa(faixa))
    for grupo, faixas in GRUPOS_ICSAP.items()
    for faixa in faixas
]


def grupo_icsap(cid: str | None) -> str | None:
    """Retorna o grupo ICSAP de um código CID-10, ou None se não for ICSAP."""
    if not cid:
        return None
    cid = _normalizar(cid)
    for grupo, inicio, fim in _FAIXAS:
        if _na_faixa(cid, inicio, fim):
            return grupo
    return None
