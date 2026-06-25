#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Injeta _snapshot.json no INITIAL_DATA do template e gera index.html."""
import sys

TEMPLATE = "Relatorio_Danone_CAC.html"
OUTPUT   = "index.html"
SNAPSHOT = "_snapshot.json"

with open(SNAPSHOT, encoding="utf-8") as f:
    snapshot = f.read().strip()

with open(TEMPLATE, encoding="utf-8") as f:
    lines = f.readlines()

out = []
replaced = False
for line in lines:
    if line.strip().startswith("const INITIAL_DATA = "):
        out.append(f"const INITIAL_DATA = {snapshot};\n")
        replaced = True
    else:
        out.append(line)

if not replaced:
    print("ERRO: padrão 'const INITIAL_DATA' não encontrado em", TEMPLATE)
    sys.exit(1)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.writelines(out)

print(f"OK: {OUTPUT} gerado a partir de {TEMPLATE} + {SNAPSHOT}")
