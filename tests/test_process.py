import pandas as pd

from evitavel.process import idade_em_anos, marcar_icsap


def test_idade_em_anos():
    cod = pd.Series([4, 5, 3, 2, 4])
    idade = pd.Series([35, 2, 11, 20, None])
    assert idade_em_anos(cod, idade).tolist()[:4] == [35, 102, 0, 0]


def test_partos_e_ano_da_internacao():
    df = pd.DataFrame({
        "MUNIC_RES": ["431490"] * 3,
        "DIAG_PRINC": ["O800", "J181", "O821"],
        "PROC_REA": ["0310010039", "0303140151", "0411010034"],
        "DT_INTER": ["20231230", "20240105", "20240210"],
        "COD_IDADE": [4, 4, 4],
        "IDADE": [25, 70, 30],
        "SEXO": ["3", "1", "3"],
        "VAL_TOT": ["500.0", "800.0", "900.0"],
        "MORTE": [0, 0, 0],
    })
    out = marcar_icsap(df)
    assert out["PARTO"].tolist() == [True, False, True]
    assert out["ICSAP"].tolist() == [False, True, False]
    assert out["ANO_INTER"].tolist() == [2023, 2024, 2024]
