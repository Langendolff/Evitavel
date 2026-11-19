"""Previsão da RME (razão de morbidade padronizada) do ano seguinte por município.

Modelo: regressão de Poisson com as ICSAP esperadas como exposição. O alvo é a
RME do ano t+1 (observado / esperado, ponderado pelo esperado, o que equivale a
um modelo de contagem com offset). As variáveis vêm do ano t e dos dois anos
anteriores:

- log da RME de t, t-1 e t-2 e dos três anos somados, cada uma encolhida em
  direção a 1 (a média do estado). O encolhimento soma K internações observadas
  e K esperadas: num município grande quase não muda nada, num pequeno puxa a
  RME para perto de 1, onde poucas internações não fazem a taxa explodir.
- log da RME da região de saúde em t.
- log da população.

Comparação de referência (persistência): a RME do ano que vem é igual à deste ano.
O modelo só vale a pena se ganhar dela na validação.

Validação: para cada ano-alvo (por exemplo 2024), o modelo é treinado só com
pares cujo alvo é anterior (até 2023) e testado no ano-alvo, como teria sido
usado na época.

Intervalo de previsão: binomial negativa em torno do valor previsto, com
variância c x mu^p estimada nos dados de treino (p sai perto de 1,4). As
contagens variam bem mais do que o acaso de Poisson (p = 1); com a forma
usual da binomial negativa (variância mu + a x mu^2) os intervalos ficavam
largos demais nos municípios grandes e estreitos demais nos médios. A
validação confere se o intervalo de 80% contém o valor real em cerca de 80%
dos municípios.

Nas regiões, a previsão é a soma das previsões dos municípios. Municípios da
mesma região variam juntos de um ano para o outro, então somar as variâncias
como se fossem independentes dá intervalos estreitos demais. O intervalo
regional é alargado por um fator estimado nos dados de treino (o desvio-padrão
dos resíduos padronizados das regiões).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import nbinom
from sklearn.linear_model import PoissonRegressor

K_ENCOLHIMENTO = 5
NIVEL_INTERVALO = 0.80
ALPHA = 1e-4


def _encolher(obs: pd.Series, esp: pd.Series) -> pd.Series:
    return (obs + K_ENCOLHIMENTO) / (esp + K_ENCOLHIMENTO)


def montar_base(municipios: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por município e ano t, com variáveis de t e o alvo de t+1."""
    m = municipios.sort_values(["MUNIC_RES", "ano"]).copy()
    reg = m.groupby(["CO_REGSAUD", "ano"])[["icsap", "icsap_esperado"]].sum()
    m = m.merge(
        (reg["icsap"] / reg["icsap_esperado"]).rename("rme_regiao").reset_index(),
        on=["CO_REGSAUD", "ano"],
    )
    m = m.sort_values(["MUNIC_RES", "ano"])
    g = m.groupby("MUNIC_RES")
    for k in (0, 1, 2):
        m[f"o{k}"] = g["icsap"].shift(k)
        m[f"e{k}"] = g["icsap_esperado"].shift(k)
    m["alvo_obs"] = g["icsap"].shift(-1)
    m["alvo_esp"] = g["icsap_esperado"].shift(-1)
    m["ano_alvo"] = m["ano"] + 1
    return m.dropna(subset=["o2"])  # precisa de três anos de história


def variaveis(base: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=base.index)
    for k in (0, 1, 2):
        x[f"log_rme_t{k}"] = np.log(_encolher(base[f"o{k}"], base[f"e{k}"]))
    x["log_rme_3anos"] = np.log(_encolher(
        base["o0"] + base["o1"] + base["o2"], base["e0"] + base["e1"] + base["e2"]
    ))
    x["log_rme_regiao"] = np.log(base["rme_regiao"])
    x["log_populacao"] = np.log(base["populacao"])
    return x


Dispersao = tuple[float, float]  # (c, p): variância = c * mu ** p
Z80 = 1.2816  # quantil de 90% da normal: intervalo central de 80%


@dataclass
class Ajuste:
    modelo: PoissonRegressor
    dispersao: Dispersao
    fator_regional: float

    def prever(self, base: pd.DataFrame) -> pd.Series:
        return pd.Series(self.modelo.predict(variaveis(base)), index=base.index)


def ajustar(treino: pd.DataFrame) -> Ajuste:
    """Ajusta o modelo e estima a variância das contagens em torno da previsão."""
    treino = treino.dropna(subset=["alvo_obs"])
    y = treino["alvo_obs"] / treino["alvo_esp"]
    modelo = PoissonRegressor(alpha=ALPHA, max_iter=2000)
    modelo.fit(variaveis(treino), y, sample_weight=treino["alvo_esp"])
    mu = modelo.predict(variaveis(treino)) * treino["alvo_esp"].to_numpy()
    resid2 = (treino["alvo_obs"].to_numpy() - mu) ** 2
    # Expoente: inclinação de log(resíduo²) contra log(mu). Constante: calibrada
    # para que o resíduo de Pearson tenha variância 1.
    p = float(np.polyfit(np.log(mu), np.log(np.maximum(resid2, 1e-3)), 1)[0])
    c = float(np.mean(resid2 / mu**p))

    por_regiao = treino.assign(mu=mu, var=variancia(mu, (c, p))).groupby(
        ["CO_REGSAUD", "ano_alvo"])[["alvo_obs", "mu", "var"]].sum()
    fator = float(np.sqrt(np.mean(
        (por_regiao["alvo_obs"] - por_regiao["mu"]) ** 2 / por_regiao["var"]
    )))
    return Ajuste(modelo, (c, p), max(fator, 1.0))


def variancia(mu, dispersao: Dispersao):
    c, p = dispersao
    return np.maximum(c * np.asarray(mu, float) ** p, np.asarray(mu, float) * 1.0001)


def intervalo(mu, dispersao: Dispersao, nivel: float = NIVEL_INTERVALO):
    """Limites do intervalo para a contagem, pela binomial negativa."""
    mu = np.asarray(mu, float)
    var = variancia(mu, dispersao)
    n, prob = mu**2 / (var - mu), mu / var
    cauda = (1 - nivel) / 2
    return nbinom.ppf(cauda, n, prob), nbinom.ppf(1 - cauda, n, prob)


def somar_regioes(mun: pd.DataFrame, ajuste: Ajuste, esp: str) -> pd.DataFrame:
    """Soma previsões municipais (coluna mu) por região, com intervalo de 80%.

    `esp` é a coluna das ICSAP esperadas que serve de denominador da RME.
    """
    mun = mun.assign(var=variancia(mun["mu"], ajuste.dispersao))
    reg = mun.groupby("CO_REGSAUD")[list(dict.fromkeys(["mu", "var", esp, "o0", "e0"]))].sum()
    dp = ajuste.fator_regional * np.sqrt(reg["var"])
    reg["rme_prevista"] = reg["mu"] / reg[esp]
    reg["rme_prev_inf80"] = (reg["mu"] - Z80 * dp) / reg[esp]
    reg["rme_prev_sup80"] = (reg["mu"] + Z80 * dp) / reg[esp]
    reg["rme_atual"] = reg["o0"] / reg["e0"]
    return reg


def _deviance(o: pd.Series, mu: pd.Series) -> float:
    o, mu = np.asarray(o, float), np.asarray(mu, float)
    termo = np.where(o > 0, o * np.log(np.where(o > 0, o, 1) / mu), 0)
    return float(2 * np.mean(termo - (o - mu)))


def validar(base: pd.DataFrame, anos_alvo: list[int], top: int = 50) -> pd.DataFrame:
    """Compara modelo e persistência ano a ano, sem olhar o futuro.

    Avalia municípios e regiões de saúde.
    """
    linhas = []
    for alvo in anos_alvo:
        ajuste = ajustar(base[base["ano_alvo"] < alvo])
        teste = base[base["ano_alvo"] == alvo].dropna(subset=["alvo_obs"])
        real = teste["alvo_obs"] / teste["alvo_esp"]
        # Para o ranking, só municípios com 20+ ICSAP esperadas: nos menores
        # a RME do ano seguinte é quase só sorte.
        relevantes = teste["alvo_esp"] >= 20
        top_real = set(real[relevantes].nlargest(top).index)
        previsoes = {"persistencia": teste["o0"] / teste["e0"], "modelo": ajuste.prever(teste)}
        for nome, rme in previsoes.items():
            mu = rme * teste["alvo_esp"]
            linha = {
                "ano_alvo": alvo,
                "nivel": "municipio",
                "metodo": nome,
                "deviance_media": _deviance(teste["alvo_obs"], mu),
                "erro_medio_rme": float(np.average((rme - real).abs(), weights=teste["alvo_esp"])),
                f"acerto_top{top}": len(top_real & set(rme[relevantes].nlargest(top).index)) / top,
            }
            if nome == "modelo":
                inf, sup = intervalo(mu, ajuste.dispersao)
                dentro = (teste["alvo_obs"] >= inf) & (teste["alvo_obs"] <= sup)
                linha["cobertura_intervalo_80"] = float(dentro.mean())
            linhas.append(linha)

            reg = somar_regioes(teste.assign(mu=mu), ajuste, "alvo_esp")
            obs_reg = teste.groupby("CO_REGSAUD")["alvo_obs"].sum()
            real_reg = obs_reg / reg["alvo_esp"]
            linha = {
                "ano_alvo": alvo,
                "nivel": "regiao",
                "metodo": nome,
                "deviance_media": _deviance(obs_reg, reg["mu"]),
                "erro_medio_rme": float(np.average(
                    (reg["rme_prevista"] - real_reg).abs(), weights=reg["alvo_esp"])),
            }
            if nome == "modelo":
                dentro = real_reg.between(reg["rme_prev_inf80"], reg["rme_prev_sup80"])
                linha["cobertura_intervalo_80"] = float(dentro.mean())
            linhas.append(linha)
    return pd.DataFrame(linhas)


def prever_proximo_ano(base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Treina com todos os pares conhecidos e prevê o ano seguinte ao último.

    As ICSAP esperadas do ano previsto ainda não existem (falta a população
    daquele ano); usa as do último ano, que mudam pouco de um ano para o outro.
    """
    ajuste = ajustar(base)
    ultimo = base[base["ano"] == base["ano"].max()].copy()
    ultimo["rme_prevista"] = ajuste.prever(ultimo)
    ultimo["mu"] = ultimo["rme_prevista"] * ultimo["e0"]
    inf, sup = intervalo(ultimo["mu"], ajuste.dispersao)
    ultimo["rme_prev_inf80"] = inf / ultimo["e0"]
    ultimo["rme_prev_sup80"] = sup / ultimo["e0"]
    ultimo["rme_atual"] = ultimo["o0"] / ultimo["e0"]
    ano_previsto = int(ultimo["ano"].iloc[0]) + 1

    colunas = ["rme_atual", "rme_prevista", "rme_prev_inf80", "rme_prev_sup80", "icsap_previstas"]
    municipios = (
        ultimo.rename(columns={"populacao": "populacao_ultimo_ano", "mu": "icsap_previstas"})
        .assign(ano_previsto=ano_previsto)
        [["ano_previsto", "MUNIC_RES", "MUNICIPIO", "CO_REGSAUD", "REGIAO_SAUDE",
          "MACRORREGIAO", "populacao_ultimo_ano", *colunas]]
        .sort_values("rme_prevista", ascending=False)
    )

    nomes = ultimo[["CO_REGSAUD", "REGIAO_SAUDE", "MACRORREGIAO"]].drop_duplicates()
    regioes = (
        somar_regioes(ultimo, ajuste, "e0")
        .rename(columns={"mu": "icsap_previstas"})
        .reset_index()
        .merge(nomes, on="CO_REGSAUD")
        .assign(ano_previsto=ano_previsto)
        [["ano_previsto", "CO_REGSAUD", "REGIAO_SAUDE", "MACRORREGIAO", *colunas]]
        .sort_values("rme_prevista", ascending=False)
    )

    coeficientes = pd.Series(ajuste.modelo.coef_, index=variaveis(ultimo).columns)
    coeficientes["intercepto"] = ajuste.modelo.intercept_
    coeficientes["variancia_c"], coeficientes["variancia_p"] = ajuste.dispersao
    coeficientes["fator_regional"] = ajuste.fator_regional
    return municipios, regioes, coeficientes
