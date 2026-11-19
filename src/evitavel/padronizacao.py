"""Padronização indireta das taxas de ICSAP por idade e sexo.

Municípios com mais idosos têm mais internações evitáveis só por isso, e a taxa
bruta (ICSAP / população) não separa esse efeito da qualidade da atenção
básica. A padronização indireta compara cada área com o estado:

    esperado = soma, em cada faixa de idade e sexo, de
               população da área na faixa x taxa do estado na faixa
    RME      = observado / esperado      (razão de morbidade padronizada)
    taxa padronizada = RME x taxa bruta do estado

RME = 1,3 quer dizer 30% mais internações evitáveis do que o esperado para a
idade e o sexo da população. A referência é o estado no mesmo ano, então a RME
mede a posição relativa da área naquele ano.

O intervalo de confiança de 95% usa a aproximação de Byar para a distribuição
de Poisson. Se o intervalo inteiro fica acima de 1, a área está acima do
esperado com pouca chance de ser só acaso; isso importa nos municípios
pequenos, onde poucas internações mudam muito a taxa.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LIMITES = list(range(0, 85, 5))  # 0-4, 5-9, ..., 75-79, 80+
ROTULOS = [f"{i:02d}-{i + 4:02d}" for i in LIMITES[:-1]] + ["80+"]
SEXO_SIH = {"1": "M", "2": "F", "3": "F"}  # SIH: 1 masc., 3 fem. (2 em anos antigos)


def faixa_etaria(idade: pd.Series) -> pd.Series:
    return pd.cut(idade, bins=LIMITES + [np.inf], right=False, labels=ROTULOS).astype(str)


def _byar(obs: pd.Series, esp: pd.Series, z: float = 1.96) -> tuple[pd.Series, pd.Series]:
    o = obs.astype(float)
    o1 = o + 1
    inf = o * (1 - 1 / (9 * o) - z / (3 * np.sqrt(o))) ** 3 / esp
    sup = o1 * (1 - 1 / (9 * o1) + z / (3 * np.sqrt(o1))) ** 3 / esp
    return inf.where(o > 0, 0.0), sup


def padronizar(
    obs: pd.DataFrame, pop: pd.DataFrame, chaves: list[str]
) -> pd.DataFrame:
    """Esperado, RME, IC 95% e taxa padronizada por área e ano.

    obs: chaves + ano + FAIXA + SEXO + icsap (contagens observadas)
    pop: chaves + ano + FAIXA + SEXO + populacao
    """
    estrato = ["ano", "FAIXA", "SEXO"]
    ref = (
        obs.groupby(estrato)["icsap"].sum().to_frame()
        .join(pop.groupby(estrato)["populacao"].sum(), how="right")
        .fillna({"icsap": 0})
    )
    ref["taxa_ref"] = ref["icsap"] / ref["populacao"]
    taxa_bruta_ref = ref.groupby("ano")["icsap"].sum() / ref.groupby("ano")["populacao"].sum()

    pop = pop.merge(ref["taxa_ref"].reset_index(), on=estrato)
    pop["esperado"] = pop["populacao"] * pop["taxa_ref"]
    out = (
        pop.groupby(chaves + ["ano"])["esperado"].sum().to_frame()
        .join(obs.groupby(chaves + ["ano"])["icsap"].sum(), how="left")
        .fillna({"icsap": 0})
        .reset_index()
    )
    out["rme"] = out["icsap"] / out["esperado"]
    out["rme_ic95_inf"], out["rme_ic95_sup"] = _byar(out["icsap"], out["esperado"])
    out["taxa_padronizada_10mil"] = 1e4 * out["rme"] * out["ano"].map(taxa_bruta_ref)
    return out.drop(columns="icsap").rename(columns={"esperado": "icsap_esperado"})
