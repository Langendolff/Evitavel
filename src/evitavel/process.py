"""Leitura dos arquivos do SIH e cálculo do indicador de ICSAP por município."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
from pyreaddbc import dbc2dbf
from dbfread import DBF

from evitavel.icsap import grupo_icsap

COLUNAS = [
    "MUNIC_RES",   # município de residência do paciente (código IBGE, 6 dígitos)
    "DIAG_PRINC",  # diagnóstico principal (CID-10)
    "DT_INTER",    # data da internação
    "IDADE",
    "SEXO",
    "VAL_TOT",     # valor pago pela internação (R$)
    "MORTE",       # 1 = óbito no hospital
    "IDENT",       # 1 = AIH normal; 5 = longa permanência (continuação)
]


def ler_dbc(caminho: Path) -> pd.DataFrame:
    """Lê um .dbc do DATASUS e devolve só as colunas usadas."""
    dbf = caminho.with_suffix(".dbf")
    if not dbf.exists():
        dbc2dbf(str(caminho), str(dbf))
    tabela = DBF(str(dbf), encoding="latin-1", load=False)
    df = pd.DataFrame(
        ({c: r.get(c) for c in COLUNAS} for r in tabela), columns=COLUNAS
    )
    # Só AIH normais: as de longa permanência repetem a mesma internação.
    return df[df["IDENT"].astype(str) == "1"].drop(columns="IDENT")


def marcar_icsap(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["GRUPO_ICSAP"] = df["DIAG_PRINC"].map(grupo_icsap)
    df["ICSAP"] = df["GRUPO_ICSAP"].notna()
    df["VAL_TOT"] = pd.to_numeric(df["VAL_TOT"], errors="coerce")
    return df


def nomes_municipios(uf: str) -> pd.DataFrame:
    """Nomes dos municípios pela API de localidades do IBGE."""
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
    dados = requests.get(url, timeout=60).json()
    return pd.DataFrame(
        {"MUNIC_RES": str(m["id"])[:6], "MUNICIPIO": m["nome"]} for m in dados
    )


def resumo_por_municipio(df: pd.DataFrame, uf: str) -> pd.DataFrame:
    """Total de internações, ICSAP e proporção de ICSAP por município."""
    df = df.assign(VAL_ICSAP=df["VAL_TOT"].where(df["ICSAP"], 0))
    resumo = (
        df.groupby("MUNIC_RES")
        .agg(
            internacoes=("ICSAP", "size"),
            icsap=("ICSAP", "sum"),
            custo_icsap_reais=("VAL_ICSAP", "sum"),
        )
        .reset_index()
    )
    resumo["proporcao_icsap_pct"] = 100 * resumo["icsap"] / resumo["internacoes"]
    resumo = resumo.merge(nomes_municipios(uf), on="MUNIC_RES", how="left")
    colunas = ["MUNIC_RES", "MUNICIPIO", "internacoes", "icsap",
               "proporcao_icsap_pct", "custo_icsap_reais"]
    return resumo[colunas].sort_values("icsap", ascending=False)
