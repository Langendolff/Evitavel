import pandas as pd
import pytest

from evitavel.padronizacao import faixa_etaria, padronizar


def test_faixas():
    assert faixa_etaria(pd.Series([0, 4, 5, 79, 80, 102])).tolist() == [
        "00-04", "00-04", "05-09", "75-79", "80+", "80+"]


def _dados():
    # Estado com dois municípios. Taxas do estado: jovens 1%, idosos 10%.
    # A tem a mesma taxa do estado em cada faixa, mas é mais velho; B é jovem.
    pop = pd.DataFrame({
        "MUNIC_RES": ["A", "A", "B", "B"],
        "ano": 2024,
        "FAIXA": ["20-24", "80+", "20-24", "80+"],
        "SEXO": "F",
        "populacao": [1000, 1000, 9000, 1000],
    })
    obs = pop.assign(icsap=[10, 100, 90, 100]).drop(columns="populacao")
    return obs, pop


def test_municipio_mais_velho_nao_fica_pior_depois_de_padronizar():
    obs, pop = _dados()
    r = padronizar(obs, pop, ["MUNIC_RES"]).set_index("MUNIC_RES")
    # Taxa bruta de A (550/10 mil) é bem maior que a de B (190/10 mil)...
    assert r.loc["A", "icsap_esperado"] == pytest.approx(110)
    # ...mas os dois têm exatamente as taxas do estado em cada faixa.
    assert r.loc["A", "rme"] == pytest.approx(1)
    assert r.loc["B", "rme"] == pytest.approx(1)
    # Taxa padronizada = taxa bruta do estado: 300 / 12 mil = 250 por 10 mil.
    assert r.loc["A", "taxa_padronizada_10mil"] == pytest.approx(250)


def test_intervalo_de_confianca():
    obs, pop = _dados()
    obs.loc[obs["MUNIC_RES"] == "A", "icsap"] *= 2  # A com o dobro
    r = padronizar(obs, pop, ["MUNIC_RES"]).set_index("MUNIC_RES")
    assert r.loc["A", "rme_ic95_inf"] < r.loc["A", "rme"] < r.loc["A", "rme_ic95_sup"]
    assert r.loc["A", "rme_ic95_inf"] > 1
