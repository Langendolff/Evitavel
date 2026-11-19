"""Leitura dos arquivos do SIH e cálculo do indicador de ICSAP por município."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import requests
from dbfread import DBF
from pyreaddbc import dbc2dbf

from evitavel.icsap import grupo_icsap
from evitavel.padronizacao import SEXO_SIH, faixa_etaria, padronizar

COLUNAS = [
    "MUNIC_RES",   # município de residência do paciente (código IBGE, 6 dígitos)
    "DIAG_PRINC",  # diagnóstico principal (CID-10)
    "PROC_REA",    # procedimento realizado (tabela SIGTAP)
    "DT_INTER",    # data da internação (AAAAMMDD)
    "COD_IDADE",   # unidade da idade: 2 dias, 3 meses, 4 anos, 5 anos + 100
    "IDADE",
    "SEXO",
    "VAL_TOT",     # valor pago pela internação (R$)
    "MORTE",       # 1 = óbito no hospital
    "IDENT",       # 1 = AIH normal; 5 = longa permanência (continuação)
]

# Partos normais (SIGTAP 03.10.01) e cesarianas (04.11.01). Saem do
# denominador da proporção de ICSAP, como é usual nos estudos: são internações
# esperadas, não sinal de falha da atenção básica.
PREFIXOS_PARTO = ("031001", "041101")


def ler_dbc(caminho: Path) -> pd.DataFrame:
    """Lê um .dbc do DATASUS e devolve só as colunas usadas, com AIH normais."""
    with tempfile.TemporaryDirectory() as tmp:
        dbf = Path(tmp) / caminho.with_suffix(".dbf").name
        dbc2dbf(str(caminho), str(dbf))
        tabela = DBF(str(dbf), encoding="latin-1", load=False)
        df = pd.DataFrame(
            ({c: r.get(c) for c in COLUNAS} for r in tabela), columns=COLUNAS
        )
    # Só AIH normais: as de longa permanência repetem a mesma internação.
    return df[df["IDENT"].astype(str) == "1"].drop(columns="IDENT")


def carregar(caminho: Path, cache: Path) -> pd.DataFrame:
    """Como ler_dbc, mas guarda o resultado em Parquet para as próximas vezes.

    Se o .dbc já foi apagado e o Parquet existe, usa o Parquet.
    """
    arquivo = cache / caminho.with_suffix(".parquet").name
    if arquivo.exists() and (
        not caminho.exists() or arquivo.stat().st_mtime >= caminho.stat().st_mtime
    ):
        return pd.read_parquet(arquivo)
    df = ler_dbc(caminho)
    cache.mkdir(parents=True, exist_ok=True)
    df.to_parquet(arquivo)
    return df


def idade_em_anos(cod_idade: pd.Series, idade: pd.Series) -> pd.Series:
    cod = pd.to_numeric(cod_idade, errors="coerce")
    idade = pd.to_numeric(idade, errors="coerce")
    anos = idade.where(cod == 4)
    anos = anos.mask(cod == 5, idade + 100)
    return anos.mask(cod.isin([1, 2, 3]), 0)  # horas, dias, meses: menos de 1 ano


def marcar_icsap(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["GRUPO_ICSAP"] = df["DIAG_PRINC"].map(grupo_icsap)
    df["ICSAP"] = df["GRUPO_ICSAP"].notna()
    df["PARTO"] = df["PROC_REA"].astype(str).str[:6].isin(PREFIXOS_PARTO)
    df["VAL_TOT"] = pd.to_numeric(df["VAL_TOT"], errors="coerce")
    df["IDADE_ANOS"] = idade_em_anos(df["COD_IDADE"], df["IDADE"])
    df["ANO_INTER"] = pd.to_numeric(df["DT_INTER"].astype(str).str[:4], errors="coerce")
    return df


def nomes_municipios(uf: str) -> pd.DataFrame:
    """Nomes dos municípios pela API de localidades do IBGE."""
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
    dados = requests.get(url, timeout=60).json()
    return pd.DataFrame(
        {"MUNIC_RES": str(m["id"])[:6], "MUNICIPIO": m["nome"]} for m in dados
    )


def contagens(df: pd.DataFrame) -> pd.DataFrame:
    """Internações por município, ano, faixa etária e sexo."""
    df = df.assign(
        VAL_ICSAP=df["VAL_TOT"].where(df["ICSAP"], 0),
        NAO_PARTO=~df["PARTO"],
        FAIXA=faixa_etaria(df["IDADE_ANOS"]),
        SEXO=df["SEXO"].astype(str).map(SEXO_SIH),
    )
    return (
        df.groupby(["MUNIC_RES", "ANO_INTER", "FAIXA", "SEXO"])
        .agg(
            internacoes=("ICSAP", "size"),
            internacoes_sem_parto=("NAO_PARTO", "sum"),
            icsap=("ICSAP", "sum"),
            custo_icsap_reais=("VAL_ICSAP", "sum"),
        )
        .reset_index()
        .rename(columns={"ANO_INTER": "ano"})
    )


def resumir(
    cont: pd.DataFrame,
    populacao: pd.DataFrame,
    territorio: pd.DataFrame,
    chaves: list[str],
) -> pd.DataFrame:
    """Indicadores de ICSAP por área (município ou região) e ano.

    `territorio` lista os municípios da UF com nome e região. Só entram os
    residentes desses municípios: pacientes de outros estados internados aqui
    não têm população de referência.

    - proporcao_icsap_pct: ICSAP / internações, sem contar partos.
    - taxa_icsap_10mil: ICSAP por 10 mil habitantes (bruta).
    - taxa_padronizada_10mil, rme: ajustadas por idade e sexo (padronizacao.py).
    """
    municipios = territorio[["MUNIC_RES", *[c for c in chaves if c != "MUNIC_RES"]]]
    cont = cont.merge(municipios, on="MUNIC_RES", how="inner")
    pop = populacao.merge(municipios, on="MUNIC_RES", how="inner")
    pop = pop.assign(FAIXA=faixa_etaria(pop["IDADE"]))

    resumo = (
        cont.groupby(chaves + ["ano"])[
            ["internacoes", "internacoes_sem_parto", "icsap", "custo_icsap_reais"]
        ].sum()
        .join(pop.groupby(chaves + ["ano"])["populacao"].sum(), how="right")
        .fillna(0)
        .reset_index()
    )
    resumo["proporcao_icsap_pct"] = 100 * resumo["icsap"] / resumo["internacoes_sem_parto"]
    resumo["taxa_icsap_10mil"] = 1e4 * resumo["icsap"] / resumo["populacao"]
    resumo = resumo.merge(padronizar(cont, pop, chaves), on=chaves + ["ano"])

    # Nomes da área: num resumo por região, as colunas do município não servem.
    por_municipio = "MUNIC_RES" in chaves
    nomes = territorio.drop(columns=[] if por_municipio else ["MUNIC_RES", "MUNICIPIO"])
    resumo = resumo.merge(nomes.drop_duplicates(chaves), on=chaves, how="left")

    id_cols = [c for c in ("ano", "MUNIC_RES", "MUNICIPIO", "CO_REGSAUD",
                           "REGIAO_SAUDE", "MACRORREGIAO") if c in resumo]
    medidas = ["populacao", "internacoes", "internacoes_sem_parto", "icsap",
               "proporcao_icsap_pct", "taxa_icsap_10mil", "icsap_esperado", "rme",
               "rme_ic95_inf", "rme_ic95_sup", "taxa_padronizada_10mil",
               "custo_icsap_reais"]
    resumo[["internacoes", "internacoes_sem_parto", "icsap", "populacao"]] = (
        resumo[["internacoes", "internacoes_sem_parto", "icsap", "populacao"]].astype(int)
    )
    return resumo[id_cols + medidas].sort_values(["ano", "icsap"], ascending=[True, False])
