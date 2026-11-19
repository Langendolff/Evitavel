"""Download dos arquivos de internação (SIH/SUS) do FTP público do DATASUS.

Arquivos "RD" (AIH reduzida): um por estado e por mês de competência,
no formato RD<UF><AA><MM>.dbc. Ex.: RDRS2401.dbc = Rio Grande do Sul, jan/2024.
"""

from __future__ import annotations

import ftplib
from pathlib import Path

FTP_HOST = "ftp.datasus.gov.br"
FTP_DIR = "/dissemin/publicos/SIHSUS/200801_/Dados"


def nome_arquivo(uf: str, ano: int, mes: int) -> str:
    return f"RD{uf.upper()}{ano % 100:02d}{mes:02d}.dbc"


def baixar_mes(uf: str, ano: int, mes: int, destino: Path) -> Path:
    """Baixa um mês de internações. Pula o download se o arquivo já existe."""
    destino.mkdir(parents=True, exist_ok=True)
    nome = nome_arquivo(uf, ano, mes)
    caminho = destino / nome
    if caminho.exists() and caminho.stat().st_size > 0:
        print(f"  {nome} já baixado")
        return caminho

    parcial = caminho.with_suffix(".part")
    with ftplib.FTP(FTP_HOST, timeout=120) as ftp:
        ftp.login()
        ftp.cwd(FTP_DIR)
        with parcial.open("wb") as f:
            ftp.retrbinary(f"RETR {nome}", f.write)
    parcial.rename(caminho)  # só vira .dbc quando o download termina inteiro
    print(f"  {nome} baixado ({caminho.stat().st_size / 1e6:.1f} MB)")
    return caminho
