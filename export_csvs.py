#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mescla os CSVs de eventtracks e tickets da pasta bases/ em _events.csv e _tickets.csv."""
import sys, glob, os

BASES = "bases"

def merge_csvs(pattern, output, delimiter):
    files = sorted(glob.glob(os.path.join(BASES, pattern)))
    if not files:
        print(f"AVISO: nenhum arquivo encontrado para '{pattern}' em '{BASES}/'")
        return 0

    header = None
    rows = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        if not lines:
            continue
        if header is None:
            header = lines[0]
        # Pula cabeçalho duplicado em arquivos seguintes
        rows.extend(l for l in lines[1:] if l.strip())

    if header is None:
        print(f"AVISO: arquivos vazios para '{pattern}'")
        return 0

    with open(output, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n")
        f.write("\n".join(rows) + "\n")

    print(f"OK {output} | {len(rows)} registros de {len(files)} arquivo(s): {[os.path.basename(p) for p in files]}")
    return len(rows)

ev = merge_csvs("*eventtracks*.csv", "_events.csv",  "|")
tk = merge_csvs("*[Tt]ickets*.csv",  "_tickets.csv", ";")

if ev == 0 and tk == 0:
    print("Nenhum CSV processado. Verifique se a pasta 'bases/' contém os arquivos.")
    sys.exit(1)
