"""Evitável: internações evitáveis (ICSAP) nos municípios a partir do SIH/SUS."""

from __future__ import annotations

import argparse
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DADOS_BRUTOS = RAIZ / "data" / "raw"
DADOS_PROCESSADOS = RAIZ / "data" / "processed"
RELATORIOS = RAIZ / "reports"


def _meses(texto: str) -> list[int]:
    """'1-12' -> [1..12]; '3' -> [3]; '1,4,7' -> [1, 4, 7]."""
    meses: list[int] = []
    for parte in texto.split(","):
        inicio, _, fim = parte.partition("-")
        meses.extend(range(int(inicio), int(fim or inicio) + 1))
    return meses


def cmd_baixar(args: argparse.Namespace) -> None:
    from evitavel.download import baixar_mes

    print(f"Baixando internações de {args.uf}, {args.ano}, meses {args.meses}")
    for mes in _meses(args.meses):
        baixar_mes(args.uf, args.ano, mes, DADOS_BRUTOS / args.uf)


def cmd_analisar(args: argparse.Namespace) -> None:
    import pandas as pd

    from evitavel.process import ler_dbc, marcar_icsap, resumo_por_municipio

    arquivos = sorted((DADOS_BRUTOS / args.uf).glob(f"RD{args.uf}{args.ano % 100:02d}*.dbc"))
    if not arquivos:
        raise SystemExit(f"Nenhum arquivo de {args.uf}/{args.ano}. Rode 'evitavel baixar' antes.")

    print(f"Lendo {len(arquivos)} arquivo(s)...")
    df = marcar_icsap(pd.concat([ler_dbc(a) for a in arquivos], ignore_index=True))

    DADOS_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DADOS_PROCESSADOS / f"internacoes_{args.uf}_{args.ano}.parquet")

    resumo = resumo_por_municipio(df, args.uf)
    RELATORIOS.mkdir(parents=True, exist_ok=True)
    saida = RELATORIOS / f"icsap_municipios_{args.uf}_{args.ano}.csv"
    resumo.to_csv(saida, index=False)

    total, icsap = len(df), int(df["ICSAP"].sum())
    print(f"\n{total:,} internações, {icsap:,} evitáveis ({100 * icsap / total:.1f}%)")
    print(f"Custo das evitáveis: R$ {df.loc[df['ICSAP'], 'VAL_TOT'].sum():,.0f}")
    print("\nGrupos mais frequentes:")
    print(df["GRUPO_ICSAP"].value_counts().head(5).to_string())
    print("\nMunicípios com mais internações evitáveis:")
    print(resumo.head(10).to_string(index=False))
    print(f"\nTabela completa: {saida}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="evitavel", description=__doc__)
    sub = parser.add_subparsers(required=True)

    for nome, func, ajuda in [
        ("baixar", cmd_baixar, "baixa os arquivos do SIH/SUS do DATASUS"),
        ("analisar", cmd_analisar, "calcula as internações evitáveis por município"),
    ]:
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("--uf", default="RS", type=str.upper)
        p.add_argument("--ano", type=int, required=True)
        if nome == "baixar":
            p.add_argument("--meses", default="1-12", help="ex.: 1-12, 3 ou 1,4,7")
        p.set_defaults(func=func)

    args = parser.parse_args()
    args.func(args)
