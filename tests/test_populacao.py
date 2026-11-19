import zipfile

from dbf_helpers import escrever_dbf

from evitavel.populacao import _ler_zip


def test_le_popsvs_filtra_uf_e_converte_sexo(tmp_path):
    dbf = tmp_path / "POP24.dbf"
    escrever_dbf(dbf, ["COD_MUN", "ANO", "SEXO", "IDADE", "POP"], [
        ("4314902", "2024", "1", "000", 100),
        ("4314902", "2024", "2", "080", 50),
        ("4205407", "2024", "1", "000", 999),  # Florianópolis, fora do RS
    ])
    caminho = tmp_path / "POPSBR24.zip"
    with zipfile.ZipFile(caminho, "w") as z:
        z.write(dbf, "POP24.dbf")
    df = _ler_zip(caminho, "RS")
    assert df.to_dict("records") == [
        {"MUNIC_RES": "431490", "ano": 2024, "SEXO": "M", "IDADE": 0, "populacao": 100},
        {"MUNIC_RES": "431490", "ano": 2024, "SEXO": "F", "IDADE": 80, "populacao": 50},
    ]
