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
    # Override botão após init() terminar de registrar seus listeners
    r"setTimeout(()=>{"
    r"const pb=document.getElementById('processBtn');"
    r"if(pb){"
    r"const pb2=pb.cloneNode(true);pb.parentNode.replaceChild(pb2,pb);"
    r"pb2.disabled=false;"
    r"pb2.addEventListener('click',async()=>{"
    r"pb2.disabled=true;"
    r"try{"
    r"const[a,b]=await Promise.all([fetch('_events.csv?r='+Math.random()),fetch('_tickets.csv?r='+Math.random())]);"
    r"if(a.ok&&b.ok){RAW.events=await a.text();RAW.tickets=await b.text();processData();}"
    r"}catch(e){}"
    r"pb2.disabled=false;"
    r"});"
    r"}},200);"
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

# Patches de métricas
PATCHES = [
    # 1. Título do card: Taxa → Autoatendimento
    (
        "Taxa de Autoatendimento",
        "Autoatendimento"
    ),
    # 2. Valor: percentual → contagem de COHORT.auto
    (
        "const rate=(COHORT.pedidos||0)>0 ? Math.round((COHORT.auto/COHORT.pedidos)*1000)/10 : 0;",
        ""
    ),
    (
        "${rate}%",
        "${fmt(COHORT.auto||0)}"
    ),
    # 3. Sub-texto: remove "X de Y resolveram" → "de Y que chegaram a pedidos"
    (
        "${fmt(COHORT.auto||0)} de ${fmt(COHORT.pedidos||0)} resolveram sem operador",
        "de ${fmt(COHORT.pedidos||0)} que chegaram a pedidos"
    ),
    # 4. Barra de progresso ainda usa ${rate}% — remove a div inteira
    (
        "${rate}%",
        "0%"
    ),
]

for old, new in PATCHES:
    if old and old not in content:
        print(f"AVISO: trecho não encontrado: {old[:60]}")
    elif old:
        content = content.replace(old, new, 1)
        print(f"OK patch: {old[:55]}...")

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(content)

print(f"OK: {OUTPUT} gerado com auto-load + patches a partir de '{SOURCE}'")
