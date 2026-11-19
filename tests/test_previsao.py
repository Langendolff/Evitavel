import numpy as np
import pandas as pd

from evitavel.previsao import ajustar, intervalo, montar_base, prever_proximo_ano, validar


def _serie(n_mun=60, anos=range(2015, 2026), seed=0):
    """Municípios com RME fixa (entre 0,6 e 1,6) e contagens de Poisson."""
    rng = np.random.default_rng(seed)
    linhas = []
    for i in range(n_mun):
        rme = 0.6 + i / n_mun
        esperado = 50 + 10 * i
        for ano in anos:
            linhas.append({
                "ano": ano, "MUNIC_RES": f"{430000 + i}", "MUNICIPIO": f"M{i}",
                "CO_REGSAUD": f"430{i % 3:02d}", "REGIAO_SAUDE": f"R{i % 3}",
                "MACRORREGIAO": "X", "populacao": 1000 * esperado,
                "icsap": rng.poisson(rme * esperado), "icsap_esperado": float(esperado),
            })
    return pd.DataFrame(linhas)


def test_base_alinha_anos_e_alvo():
    base = montar_base(_serie())
    linha = base[(base["MUNIC_RES"] == "430005") & (base["ano"] == 2020)].iloc[0]
    serie = _serie().set_index(["MUNIC_RES", "ano"])["icsap"]
    assert linha["o0"] == serie[("430005", 2020)]
    assert linha["o2"] == serie[("430005", 2018)]
    assert linha["alvo_obs"] == serie[("430005", 2021)]
    assert base["ano"].min() == 2017  # precisa de três anos de história


def test_modelo_recupera_rme_estavel_e_ganha_da_persistencia():
    base = montar_base(_serie())
    aval = validar(base, [2024, 2025]).query("nivel == 'municipio'")
    media = aval.groupby("metodo")["deviance_media"].mean()
    assert media["modelo"] < media["persistencia"]  # média de anos > um ano só

    mun, reg, _ = prever_proximo_ano(base)
    assert mun["ano_previsto"].unique().tolist() == [2026]
    real = 0.6 + mun["MUNIC_RES"].str[-2:].astype(int) / 60
    assert np.average((mun["rme_prevista"] - real).abs()) < 0.06
    assert len(reg) == 3


def test_intervalo_contem_a_previsao():
    ajuste = ajustar(montar_base(_serie()))
    inf, sup = intervalo(np.array([10.0, 100.0, 1000.0]), ajuste.dispersao)
    assert (inf <= [10, 100, 1000]).all() and (sup >= [10, 100, 1000]).all()
    assert (sup - inf)[2] > (sup - inf)[0]
