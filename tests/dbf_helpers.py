"""Escreve um .dbf mínimo (campos texto e numéricos) para os testes."""

import struct
from datetime import date


def escrever_dbf(caminho, campos, linhas):
    tipos = ["N" if isinstance(v, int) else "C" for v in linhas[0]]
    larguras = [max(len(str(l[i])) for l in linhas) + 1 for i in range(len(campos))]
    hoje = date.today()
    tam_cab = 32 + 32 * len(campos) + 1
    tam_reg = 1 + sum(larguras)
    with open(caminho, "wb") as f:
        f.write(struct.pack("<BBBBIHH20x", 3, hoje.year - 1900, hoje.month, hoje.day,
                            len(linhas), tam_cab, tam_reg))
        for nome, tipo, larg in zip(campos, tipos, larguras):
            f.write(struct.pack("<11sc4xBB14x", nome.encode(), tipo.encode(), larg, 0))
        f.write(b"\r")
        for linha in linhas:
            f.write(b" ")
            for v, tipo, larg in zip(linha, tipos, larguras):
                texto = str(v)
                f.write((texto.rjust(larg) if tipo == "N" else texto.ljust(larg)).encode())
        f.write(b"\x1a")
