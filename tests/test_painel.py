from evitavel.painel import _caminho, contornos_regionais, projetar


def _quadrado(x, y):
    return [[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1], [x, y]]


def _malha(*quadrados):
    return {"features": [
        {"properties": {"codarea": cod + "0"},
         "geometry": {"type": "Polygon", "coordinates": [_quadrado(x, y)]}}
        for cod, x, y in quadrados
    ]}


def test_projecao_mantem_proporcao_e_norte_para_cima():
    aneis, altura = projetar(_malha(("430001", -50, -30), ("430002", -49, -30)))
    xs = [p[0] for anel in aneis.values() for p in anel[0]]
    assert min(xs) == 0 and max(xs) == 1000
    # dois graus de longitude por um de latitude, encurtados pelo cosseno de 29,5°
    assert 550 < altura < 590
    # o canto norte (lat -29) fica em cima (y = 0)
    assert min(p[1] for p in aneis["430001"][0]) == 0


def test_contorno_regional_cancela_fronteira_interna():
    aneis, _ = projetar(_malha(("430001", -50, -30), ("430002", -49, -30), ("430003", -48, -30)))
    contornos = contornos_regionais(aneis, {"430001": "A", "430002": "A", "430003": "B"})
    # região A: dois quadrados lado a lado -> 6 arestas externas (a do meio some)
    assert contornos["A"].count("M") == 6
    assert contornos["B"].count("M") == 4


def test_caminho_remove_pontos_repetidos():
    assert _caminho([[(0, 0), (0, 0), (1, 0), (1, 1)]]) == "M0,0L1,0L1,1Z"
