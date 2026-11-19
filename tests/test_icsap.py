from evitavel.icsap import grupo_icsap


def test_faixa_de_categorias_inclui_subcategorias():
    assert grupo_icsap("A09").startswith("02")
    assert grupo_icsap("A090").startswith("02")
    assert grupo_icsap("E14.9").startswith("13")


def test_faixa_de_subcategorias_e_exata():
    assert grupo_icsap("J181").startswith("06")
    assert grupo_icsap("J180") is None  # broncopneumonia não especificada fica fora
    assert grupo_icsap("N390").startswith("15")
    assert grupo_icsap("N391") is None


def test_codigos_fora_da_lista():
    assert grupo_icsap("S72") is None  # fratura de fêmur
    assert grupo_icsap("O80") is None  # parto normal
    assert grupo_icsap("") is None
    assert grupo_icsap(None) is None


def test_limites_das_faixas():
    assert grupo_icsap("I10").startswith("09")
    assert grupo_icsap("I11.9").startswith("09")
    assert grupo_icsap("I12") is None
