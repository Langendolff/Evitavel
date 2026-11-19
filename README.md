# Evitável

Identifica **internações evitáveis** nos municípios do Rio Grande do Sul a partir
dos dados públicos do SUS.

Internações por condições sensíveis à atenção primária (ICSAP) são as que
poderiam ter sido evitadas com um bom atendimento no posto de saúde: diabetes,
hipertensão, asma, pneumonias bacterianas, infecções urinárias, entre outras.
Uma proporção alta de ICSAP num município indica que a atenção básica de lá
precisa de reforço.

**Objetivo:** prever quais municípios ou regiões vão ter mais internações
evitáveis, para ajudar gestores de saúde a decidir onde investir.

## Status

Fase 1: baixar os dados e calcular o indicador atual por município.

## Como rodar

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync

# Baixa as internações do RS em 2024 (um arquivo por mês, ~10 MB cada)
uv run evitavel baixar --uf RS --ano 2024

# Ou só alguns meses, para testar
uv run evitavel baixar --uf RS --ano 2024 --meses 1

# Calcula as internações evitáveis por município
uv run evitavel analisar --uf RS --ano 2024

# Testes
uv run pytest
```

O resultado vai para `reports/icsap_municipios_RS_<ano>.csv`, e a base completa
com cada internação marcada vai para `data/processed/`.

## Estrutura

| Caminho | Conteúdo |
| --- | --- |
| `src/evitavel/icsap.py` | Lista brasileira de ICSAP (19 grupos de CID-10) |
| `src/evitavel/download.py` | Download dos arquivos do SIH/SUS do FTP do DATASUS |
| `src/evitavel/process.py` | Leitura dos arquivos e resumo por município |
| `src/evitavel/__init__.py` | Comandos `baixar` e `analisar` |
| `data/raw/` | Arquivos `.dbc` baixados (fora do git) |
| `data/processed/` | Bases tratadas em Parquet (fora do git) |
| `reports/` | Tabelas de resultado |
| `tests/` | Testes |

## Dados

- **SIH/SUS (arquivos RD):** uma linha por internação paga pelo SUS. Não
  identifica pacientes. Fonte: FTP público do DATASUS.
- **Municípios:** nomes pela API de localidades do IBGE.

## Limitações conhecidas

- Os arquivos são organizados pelo **mês de processamento** da internação,
  não pelo mês em que ela aconteceu. Algumas internações de dezembro aparecem
  nos arquivos de janeiro do ano seguinte.
- Só cobre internações pagas pelo SUS. Internações por planos de saúde ficam
  de fora.
- A proporção de ICSAP é calculada sobre todas as internações. Estudos
  costumam excluir partos do denominador; isso ainda não foi feito.
- A lista de CIDs em `icsap.py` segue a [Portaria SAS/MS nº 221/2008](https://bvsms.saude.gov.br/bvs/saudelegis/sas/2008/prt0221_17_04_2008.html),
  conferida com o texto publicado no site do Ministério da Saúde.

## Primeiros resultados (RS, 2024)

| Indicador | Valor |
| --- | --- |
| Internações pelo SUS | 827.109 |
| Internações evitáveis (ICSAP) | 136.131 (16,5%) |
| Custo das evitáveis | R$ 210 milhões |
| Causas mais comuns | Doenças cerebrovasculares, doenças pulmonares, insuficiência cardíaca, infecção urinária, pneumonias bacterianas |

## Próximos passos

1. Baixar a população dos municípios (IBGE) e calcular taxas por 10 mil habitantes
2. Montar uma série histórica de 2015 em diante
3. Treinar um primeiro modelo de previsão por município e região de saúde
4. Fazer um mapa ou painel para mostrar os resultados
5. Apresentar para um grupo de pesquisa em saúde pública ou para o COSEMS-RS
