"""Regiões e macrorregiões de saúde de cada município.

Fonte: base territorial do DATASUS (ftp.datasus.gov.br/territorio/tabelas),
a mesma usada pelo TabNet. Baixa a versão mais recente disponível.
"""

from __future__ import annotations

import ftplib
import io
import zipfile
from pathlib import Path

import pandas as pd

from evitavel.populacao import CODIGO_UF

FTP_HOST = "ftp.datasus.gov.br"
FTP_DIR = "/territorio/tabelas"


def _baixar_base(destino: Path) -> Path:
    with ftplib.FTP(FTP_HOST, timeout=120) as ftp:
        ftp.login()
        ftp.cwd(FTP_DIR)
        ano = max(d for d in ftp.nlst() if d.isdigit())
        ftp.cwd(ano)
        nome = sorted(n for n in ftp.nlst() if "base_territorial" in n)[-1]
        destino.mkdir(parents=True, exist_ok=True)
        caminho = destino / nome
        if not caminho.exists():
            with caminho.open("wb") as f:
                ftp.retrbinary(f"RETR {nome}", f.write)
            print(f"  {nome} baixado")
    return caminho


def _csv(z: zipfile.ZipFile, nome: str) -> pd.DataFrame:
    texto = z.read(nome).decode("utf-8-sig")
    sep = ";" if texto.splitlines()[0].count(";") else ","
    return pd.read_csv(io.StringIO(texto), sep=sep, dtype=str)


def ler_regioes(caminho_zip: Path, uf: str) -> pd.DataFrame:
    prefixo = str(CODIGO_UF[uf])
    with zipfile.ZipFile(caminho_zip) as z:
        nomes = {Path(n).name: n for n in z.namelist()}
        mun_reg = _csv(z, nomes["rl_municip_regsaud.csv"])
        mun_mac = _csv(z, nomes["rl_municip_macsaud.csv"])
        regioes = _csv(z, nomes["tb_regsaud.csv"])[["CO_REGSAUD", "DS_NOME"]]
        macros = _csv(z, nomes["tb_macsaud.csv"])[["CO_MACSAUD", "DS_NOME"]]
    df = (
        mun_reg.merge(mun_mac, on="CO_MUNICIP")
        .merge(regioes.rename(columns={"DS_NOME": "REGIAO_SAUDE"}), on="CO_REGSAUD")
        .merge(macros.rename(columns={"DS_NOME": "MACRORREGIAO"}), on="CO_MACSAUD")
        .rename(columns={"CO_MUNICIP": "MUNIC_RES"})
    )
    df = df[df["MUNIC_RES"].str.startswith(prefixo)]
    # "Região 10 - Capital e Vale do Gravataí - RS" -> "Região 10 - Capital e Vale do Gravataí"
    df["REGIAO_SAUDE"] = df["REGIAO_SAUDE"].str.removesuffix(f" - {uf}")
    df["MACRORREGIAO"] = df["MACRORREGIAO"].str.title()
    return df[["MUNIC_RES", "CO_REGSAUD", "REGIAO_SAUDE", "MACRORREGIAO"]]


def regioes_de_saude(uf: str, brutos: Path, cache: Path) -> pd.DataFrame:
    arquivo = cache / f"regioes_saude_{uf}.parquet"
    if not arquivo.exists():
        cache.mkdir(parents=True, exist_ok=True)
        ler_regioes(_baixar_base(brutos), uf).to_parquet(arquivo)
    return pd.read_parquet(arquivo)
