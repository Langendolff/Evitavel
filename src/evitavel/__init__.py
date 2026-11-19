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


def _anos(texto: str) -> list[int]:
    return _meses(texto)  # mesmo formato: '2024', '2015-2025', '2019,2024'


def _cache_sih(uf: str) -> Path:
    return DADOS_PROCESSADOS / "sih" / uf


def _arquivos_do_ano(uf: str, ano: int) -> tuple[list[Path], list[str]]:
    """Arquivos que podem conter internações ocorridas em `ano`.

    Os arquivos são por mês de processamento: uma internação de dezembro pode
    ser processada meses depois. Por isso entram os 12 meses do ano e os do ano
    seguinte. Devolve também os meses que faltam baixar.
    """
    from evitavel.download import nome_arquivo

    existentes, faltando = [], []
    for a in (ano, ano + 1):
        for mes in range(1, 13):
            caminho = DADOS_BRUTOS / uf / nome_arquivo(uf, a, mes)
            em_cache = (_cache_sih(uf) / caminho.with_suffix(".parquet").name).exists()
            if caminho.exists() or em_cache:
                existentes.append(caminho)
            elif a == ano or mes <= 6:
                faltando.append(caminho.stem)
    return existentes, faltando


def cmd_analisar(args: argparse.Namespace) -> None:
    import pandas as pd

    from evitavel.populacao import populacao_por_idade
    from evitavel.process import (carregar, contagens, marcar_icsap,
                                  nomes_municipios, resumir)
    from evitavel.territorio import regioes_de_saude

    anos = _anos(args.anos)
    arquivos: set[Path] = set()
    for ano in anos:
        existentes, faltando = _arquivos_do_ano(args.uf, ano)
        if not any(a.stem[-4:-2] == f"{ano % 100:02d}" for a in existentes):
            raise SystemExit(f"Nenhum arquivo de {args.uf}/{ano}. Rode 'evitavel baixar' antes.")
        if faltando:
            print(f"Aviso: {ano} pode estar incompleto, faltam {', '.join(faltando)}")
        arquivos.update(existentes)

    print(f"Lendo {len(arquivos)} arquivo(s)...")
    cache = _cache_sih(args.uf)
    df = pd.concat([carregar(a, cache) for a in sorted(arquivos)], ignore_index=True)
    df = marcar_icsap(df)
    df = df[df["ANO_INTER"].isin(anos)]

    cont = contagens(df)
    pop = populacao_por_idade(args.uf, anos, DADOS_BRUTOS / "popsvs", DADOS_PROCESSADOS)
    territorio = nomes_municipios(args.uf).merge(
        regioes_de_saude(args.uf, DADOS_BRUTOS, DADOS_PROCESSADOS), on="MUNIC_RES"
    )
    municipios = resumir(cont, pop, territorio, ["MUNIC_RES"])
    regioes = resumir(cont, pop, territorio, ["CO_REGSAUD"])

    RELATORIOS.mkdir(parents=True, exist_ok=True)
    periodo = str(anos[0]) if len(anos) == 1 else f"{min(anos)}-{max(anos)}"
    saidas = []
    for nome, tabela in [("municipios", municipios), ("regioes", regioes)]:
        saida = RELATORIOS / f"icsap_{nome}_{args.uf}_{periodo}.csv"
        tabela.to_csv(saida, index=False)
        saidas.append(saida)

    print("\nPor ano (residentes do estado):")
    por_ano = municipios.groupby("ano")[["internacoes_sem_parto", "icsap",
                                         "custo_icsap_reais", "populacao"]].sum()
    por_ano["proporcao_pct"] = 100 * por_ano["icsap"] / por_ano["internacoes_sem_parto"]
    por_ano["taxa_10mil"] = 1e4 * por_ano["icsap"] / por_ano["populacao"]
    print(por_ano.round(1).to_string())

    ultimo = max(anos)
    colunas = ["populacao", "icsap", "taxa_icsap_10mil", "taxa_padronizada_10mil",
               "rme", "rme_ic95_inf", "rme_ic95_sup"]
    print(f"\nRegiões de saúde em {ultimo}, da maior para a menor RME:")
    print(regioes[regioes["ano"] == ultimo].sort_values("rme", ascending=False)[
        ["REGIAO_SAUDE"] + colunas].round(2).to_string(index=False))

    acima = municipios[(municipios["ano"] == ultimo)
                       & (municipios["populacao"] >= args.pop_minima)
                       & (municipios["rme_ic95_inf"] > 1)]
    print(f"\nMunicípios com {args.pop_minima:,}+ habitantes claramente acima do "
          f"esperado em {ultimo} ({len(acima)} no total, 10 maiores RME):")
    print(acima.nlargest(10, "rme")[["MUNICIPIO", "REGIAO_SAUDE"] + colunas]
          .round(2).to_string(index=False))
    print("\nTabelas completas:\n" + "\n".join(f"  {s}" for s in saidas))


def main() -> None:
    parser = argparse.ArgumentParser(prog="evitavel", description=__doc__)
    sub = parser.add_subparsers(required=True)

    for nome, func, ajuda in [
        ("baixar", cmd_baixar, "baixa os arquivos do SIH/SUS do DATASUS"),
        ("analisar", cmd_analisar, "calcula as internações evitáveis por município"),
    ]:
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("--uf", default="RS", type=str.upper)
        if nome == "baixar":
            p.add_argument("--ano", type=int, required=True)
            p.add_argument("--meses", default="1-12", help="ex.: 1-12, 3 ou 1,4,7")
        else:
            p.add_argument("--anos", required=True, help="ex.: 2024, 2015-2025")
        if nome != "baixar":
            p.add_argument("--pop-minima", type=int, default=20_000,
                           help="população mínima no ranking da tela (padrão: 20000)")
        p.set_defaults(func=func)

    args = parser.parse_args()
    args.func(args)
