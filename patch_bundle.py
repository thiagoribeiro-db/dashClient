#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera index.html a partir do bundle Claude Design, injetando auto-load de CSVs
e ocultando o painel de pasta (não necessário para o cliente)."""
import sys

SOURCE = "Danone CAC - Painel.html"
OUTPUT = "index.html"

with open(SOURCE, encoding="utf-8") as f:
    content = f.read()

# Código de auto-load injetado no início da função init.
# Usa \n literal (igual ao bundle) e aspas simples (sem necessidade de escape).
AUTO_LOAD = (
    r"  try{"
    r"const [evR,tkR]=await Promise.all([fetch('_events.csv'),fetch('_tickets.csv')]);"
    r"if(evR.ok&&tkR.ok){"
    r"RAW.events=await evR.text();RAW.tickets=await tkR.text();"
    r"const fp=document.getElementById('folderPanel');if(fp)fp.style.display='none';"
    r"const mw=document.getElementById('manualWrap');if(mw)mw.style.display='none';"
    r"processData();"
    r"}}catch(e){}"
)

MARKER = r"(async function init(){\n"
if MARKER not in content:
    # Tenta com newline real (caso o bundle mude de formato)
    MARKER = "(async function init(){\n"
    if MARKER not in content:
        print("ERRO: marcador '(async function init()' não encontrado no bundle.")
        sys.exit(1)

content = content.replace(MARKER, MARKER + AUTO_LOAD + r"\n", 1)

# Patch: KPI de Atendimento usa total de registros (sem deduplicação de usuário)
PATCHES = [
    (
        "value:TK.users.size, sub:'Atendidos por humano'",
        "value:TK.rows.length, sub:'Total de atendimentos'"
    ),
]

for old, new in PATCHES:
    if old not in content:
        print(f"AVISO: trecho não encontrado para patch: {old[:60]}")
    else:
        content = content.replace(old, new, 1)
        print(f"OK patch: {old[:50]}...")

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(content)

print(f"OK: {OUTPUT} gerado com auto-load + patches a partir de '{SOURCE}'")
