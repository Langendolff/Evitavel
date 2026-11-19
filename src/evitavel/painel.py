"""Painel em HTML: mapa, série histórica e previsão por município e região.

Gera um único arquivo autocontido (dados, mapa e código juntos), que abre sem
internet e pode ser mandado por e-mail. O modelo da página fica em
painel_modelo.html; aqui só se preparam os dados e a geometria.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd
import requests

from evitavel.populacao import CODIGO_UF

MALHAS = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
LARGURA = 1000  # largura do mapa em unidades do SVG


def baixar_malha(uf: str, destino: Path) -> dict:
    """Contornos dos municípios (GeoJSON do IBGE), com cache local."""
    arquivo = destino / f"municipios_{uf}.json"
    if not arquivo.exists():
        destino.mkdir(parents=True, exist_ok=True)
        resposta = requests.get(
            MALHAS.format(uf=CODIGO_UF[uf]),
            params={"formato": "application/vnd.geo+json",
                    "intrarregiao": "municipio", "qualidade": "intermediaria"},
            timeout=120,
        )
        resposta.raise_for_status()
        arquivo.write_bytes(resposta.content)
    return json.loads(arquivo.read_text())


def _aneis(geometria: dict) -> list[list[list[float]]]:
    if geometria["type"] == "Polygon":
        return geometria["coordinates"]
    return [anel for poligono in geometria["coordinates"] for anel in poligono]


def projetar(malha: dict) -> tuple[dict[str, list[list[tuple[float, float]]]], float]:
    """Projeção equiretangular com a escala de longitude corrigida pela latitude.

    Devolve os anéis de cada município em coordenadas do SVG e a altura do mapa.
    """
    pontos = [p for f in malha["features"] for anel in _aneis(f["geometry"]) for p in anel]
    lons, lats = [p[0] for p in pontos], [p[1] for p in pontos]
    fator = math.cos(math.radians((min(lats) + max(lats)) / 2))
    x0, y1 = min(lons) * fator, max(lats)
    escala = LARGURA / (max(lons) * fator - x0)

    aneis = {}
    for f in malha["features"]:
        codigo = f["properties"]["codarea"][:6]
        aneis[codigo] = [
            [(round((lon * fator - x0) * escala, 1), round((y1 - lat) * escala, 1))
             for lon, lat in anel]
            for anel in _aneis(f["geometry"])
        ]
    return aneis, round((max(lats) - min(lats)) * escala, 1)


def _caminho(aneis: list[list[tuple[float, float]]]) -> str:
    partes = []
    for anel in aneis:
        limpo = [p for i, p in enumerate(anel) if i == 0 or p != anel[i - 1]]
        partes.append("M" + "L".join(f"{x:g},{y:g}" for x, y in limpo) + "Z")
    return "".join(partes)


def contornos_regionais(aneis: dict, regiao_de: dict[str, str]) -> dict[str, str]:
    """Contorno de cada região: as arestas que não são compartilhadas por dois
    municípios da mesma região. Os vizinhos na malha do IBGE usam os mesmos
    vértices, então a aresta interna aparece duas vezes e se cancela."""
    arestas: dict[str, Counter] = {}
    for codigo, lista in aneis.items():
        regiao = regiao_de.get(codigo)
        if regiao is None:
            continue
        contagem = arestas.setdefault(regiao, Counter())
        for anel in lista:
            for a, b in zip(anel, anel[1:]):
                if a != b:
                    contagem[tuple(sorted((a, b)))] += 1
    return {
        regiao: "".join(f"M{a[0]:g},{a[1]:g}L{b[0]:g},{b[1]:g}"
                        for (a, b), n in contagem.items() if n == 1)
        for regiao, contagem in arestas.items()
    }


def _registros(df: pd.DataFrame, colunas: dict[str, str], casas: int = 3) -> list[dict]:
    saida = df[list(colunas)].rename(columns=colunas)
    for c in saida.select_dtypes("float").columns:
        saida[c] = saida[c].round(casas)
    return json.loads(saida.to_json(orient="records"))


def montar_dados(serie_mun: pd.DataFrame, serie_reg: pd.DataFrame,
                 prev_mun: pd.DataFrame, prev_reg: pd.DataFrame,
                 aneis: dict, altura: float) -> dict:
    regiao_de = dict(zip(serie_mun["MUNIC_RES"], serie_mun["CO_REGSAUD"]))
    medidas = {"ano": "ano", "populacao": "pop", "icsap": "obs",
               "icsap_esperado": "esp", "rme": "rme", "rme_ic95_inf": "lo",
               "rme_ic95_sup": "hi", "taxa_icsap_10mil": "taxa",
               "taxa_padronizada_10mil": "taxa_pad", "custo_icsap_reais": "custo",
               "proporcao_icsap_pct": "prop"}
    previsao = {"rme_prevista": "rme", "rme_prev_inf80": "lo",
                "rme_prev_sup80": "hi", "icsap_previstas": "obs"}

    municipios = {}
    for codigo, g in serie_mun.sort_values("ano").groupby("MUNIC_RES"):
        primeira = g.iloc[0]
        municipios[codigo] = {
            "nome": primeira["MUNICIPIO"],
            "regiao": primeira["CO_REGSAUD"],
            "caminho": _caminho(aneis[codigo]) if codigo in aneis else None,
            "serie": _registros(g, medidas),
        }
    for r in _registros(prev_mun, {"MUNIC_RES": "codigo", **previsao}):
        municipios[r.pop("codigo")]["previsao"] = r

    regioes = {}
    for codigo, g in serie_reg.sort_values("ano").groupby("CO_REGSAUD"):
        primeira = g.iloc[0]
        regioes[codigo] = {
            "nome": primeira["REGIAO_SAUDE"],
            "macro": primeira["MACRORREGIAO"],
            "serie": _registros(g, medidas),
        }
    for r in _registros(prev_reg, {"CO_REGSAUD": "codigo", **previsao}):
        regioes[r.pop("codigo")]["previsao"] = r

    estado = (
        serie_mun.groupby("ano")[["icsap", "populacao", "internacoes_sem_parto",
                                  "custo_icsap_reais"]].sum().reset_index()
    )
    estado["taxa"] = 1e4 * estado["icsap"] / estado["populacao"]
    estado["prop"] = 100 * estado["icsap"] / estado["internacoes_sem_parto"]

    return {
        "largura": LARGURA,
        "altura": altura,
        "anos": sorted(int(a) for a in serie_mun["ano"].unique()),
        "ano_previsto": int(prev_mun["ano_previsto"].iloc[0]),
        "municipios": municipios,
        "regioes": regioes,
        "contornos": contornos_regionais(aneis, regiao_de),
        "estado": _registros(estado, {"ano": "ano", "icsap": "obs", "populacao": "pop",
                                      "taxa": "taxa", "prop": "prop",
                                      "custo_icsap_reais": "custo"}),
    }


def gerar_painel(uf: str, relatorios: Path, brutos: Path, periodo: str) -> Path:
    leitura = {"dtype": {"MUNIC_RES": str, "CO_REGSAUD": str}}
    serie_mun = pd.read_csv(relatorios / f"icsap_municipios_{uf}_{periodo}.csv", **leitura)
    serie_reg = pd.read_csv(relatorios / f"icsap_regioes_{uf}_{periodo}.csv", **leitura)
    ano_prev = int(serie_mun["ano"].max()) + 1
    prev_mun = pd.read_csv(relatorios / f"previsao_municipios_{uf}_{ano_prev}.csv", **leitura)
    prev_reg = pd.read_csv(relatorios / f"previsao_regioes_{uf}_{ano_prev}.csv", **leitura)

    aneis, altura = projetar(baixar_malha(uf, brutos / "malhas"))
    dados = montar_dados(serie_mun, serie_reg, prev_mun, prev_reg, aneis, altura)

    modelo = (Path(__file__).parent / "painel_modelo.html").read_text()
    html = (modelo.replace("__UF__", uf)
            .replace("__DADOS__", json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
                     .replace("</", "<\\/")))  # nada no JSON fecha o <script>
    saida = relatorios / f"painel_icsap_{uf}.html"
    saida.write_text(html)
    return saida
