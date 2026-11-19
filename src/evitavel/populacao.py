"""População residente por município, sexo e idade (estimativas do Ministério da Saúde).

Fonte: arquivos POPSVS do DATASUS, as mesmas estimativas que o TabNet usa nos
indicadores oficiais. Cobrem 2000-2025, com idade simples de 0 a 80+ e sexo,
e foram refeitas depois do Censo 2022, então formam uma série contínua.

Por que não as estimativas anuais do IBGE (tabela 6579 da SIDRA): as de
2011-2021 vêm do Censo 2010 e superestimaram muitos municípios, e as de 2024
em diante corrigem a subcontagem do Censo 2022. Misturar as duas, ou interpolar
entre os censos, cria saltos falsos na série. O POPSVS coincide com o IBGE a
partir de 2024 e é suave antes disso.
"""

from __future__ import annotations

import ftplib
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
from dbfread import DBF

FTP_HOST = "ftp.datasus.gov.br"
FTP_DIR = "/dissemin/publicos/IBGE/POPSVS"
CODIGO_UF = {
    "RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17,
    "MA": 21, "PI": 22, "CE": 23, "RN": 24, "PB": 25, "PE": 26, "AL": 27,
    "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35, "PR": 41,
    "SC": 42, "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53,
}


def _baixar_zip(ano: int, destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"POPSBR{ano % 100:02d}.zip"
    if caminho.exists() and caminho.stat().st_size > 0:
        return caminho
    parcial = caminho.with_suffix(".part")
    with ftplib.FTP(FTP_HOST, timeout=120) as ftp:
        ftp.login()
        ftp.cwd(FTP_DIR)
        with parcial.open("wb") as f:
            ftp.retrbinary(f"RETR {caminho.name}", f.write)
    parcial.rename(caminho)
    print(f"  {caminho.name} baixado")
    return caminho


def _ler_zip(caminho: Path, uf: str) -> pd.DataFrame:
    prefixo = str(CODIGO_UF[uf])
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(caminho) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".dbf"))
        dbf = z.extract(nome, tmp)
        linhas = (
            {k.upper(): v for k, v in r.items()}
            for r in DBF(dbf, encoding="latin-1", load=False)
        )
        df = pd.DataFrame(l for l in linhas if str(l["COD_MUN"]).startswith(prefixo))
    return pd.DataFrame({
        "MUNIC_RES": df["COD_MUN"].astype(str).str[:6],
        "ano": df["ANO"].astype(int),
        # POPSVS: 1 = masculino, 2 = feminino. No SIH é 1 e 3.
        "SEXO": df["SEXO"].astype(str).map({"1": "M", "2": "F"}),
        "IDADE": df["IDADE"].astype(int),  # 80 = 80 anos ou mais
        "populacao": df["POP"].astype(int),
    })


def populacao_por_idade(uf: str, anos: list[int], brutos: Path, cache: Path) -> pd.DataFrame:
    """População por município, ano, sexo e idade simples (com cache local)."""
    partes = []
    for ano in anos:
        arquivo = cache / f"populacao_{uf}_{ano}.parquet"
        if not arquivo.exists():
            cache.mkdir(parents=True, exist_ok=True)
            _ler_zip(_baixar_zip(ano, brutos), uf).to_parquet(arquivo)
        partes.append(pd.read_parquet(arquivo))
    return pd.concat(partes, ignore_index=True)
