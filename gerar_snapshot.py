#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Snapshot unificado (OnePage + Detalhamento) -> _snapshot.json
Chaves de ambiente: BLIP_ROUTER_KEY (router/analytics/event-track) e BLIP_TRANSBORDO_KEY (desk).
Horários UTC/Londres -> Brasília (UTC-3)."""
import os, sys, json, urllib.request, urllib.parse, time, re
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone

ENDPOINT="https://msging.net/commands"
ANALYTICS="postmaster@analytics.msging.net"; CRM="postmaster@crm.msging.net"; DESK="postmaster@desk.msging.net"
BR=timezone(timedelta(hours=-3)); UTC=timezone.utc
RKEY=os.environ.get("BLIP_ROUTER_KEY","").strip()
TKEY=os.environ.get("BLIP_TRANSBORDO_KEY","").strip()
if not RKEY: print("ERRO: defina BLIP_ROUTER_KEY"); sys.exit(1)
START=os.environ.get("BLIP_START","2026-05-20")
END=os.environ.get("BLIP_END", datetime.now(BR).strftime("%Y-%m-%d"))
GEN_TS=datetime.now(BR).strftime("%d/%m/%Y %H:%M")
P0=datetime.fromisoformat(START+"T00:00:00+00:00"); P1=datetime.fromisoformat(END+"T23:59:59+00:00")

def cmd(uri,to,key=RKEY):
    b={"id":str(time.time())+str(time.perf_counter()),"method":"get","uri":uri,"to":to}
    r=urllib.request.Request(ENDPOINT,data=json.dumps(b).encode(),
        headers={"Content-Type":"application/json","Authorization":"Key "+key})
    err=""
    for _ in range(3):
        try:
            with urllib.request.urlopen(r,timeout=70) as x: return json.loads(x.read().decode())
        except Exception as e: err=str(e); time.sleep(1)
    return {"status":"error","reason":err}
def dparse(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(UTC)
    except: return None

# ============ MÉTRICAS ONEPAGE ============
msg=cmd("/metrics/messages?startDate=%s&endDate=%s"%(START,END),ANALYTICS).get("resource",{})
act=cmd("/metrics/active-identity-quantity?startDate=%s&endDate=%s"%(START,END),ANALYTICS).get("resource",{}).get("count")
eng=cmd("/metrics/engaged-identity-quantity?startDate=%s&endDate=%s"%(START,END),ANALYTICS).get("resource",{}).get("count")
rec=cmd("/metrics/recurrence?startDate=%s&endDate=%s"%(START,END),ANALYTICS).get("resource",{})
flow=cmd("/flowmetrics?startDate=%s&endDate=%s"%(START,END),ANALYTICS).get("resource",{})
blocks=cmd("/blocks/fallback?startDate=%s&endDate=%s"%(START,END),ANALYTICS).get("resource",{}).get("items",[])

# ============ EVENT-TRACK (KPIs + jornadas) ============
cats=[it["category"] for it in cmd("/event-track?$take=500",ANALYTICS).get("resource",{}).get("items",[])]
ISO_FULL=re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"); DATE_ONLY=re.compile(r"^\d{4}-\d{2}-\d{2}$")
def parse_action(a):
    parts=[p.strip() for p in (a or "").split("|")]
    phone=date_s=full=hour=None; vals=[]
    for p in parts:
        if phone is None:
            d=p.split("@")[0].strip()
            if d.isdigit() and 12<=len(d)<=13 and d.startswith("55"): phone=d; continue
        if full is None and ISO_FULL.match(p): full=p; continue
        if date_s is None and DATE_ONLY.match(p): date_s=p; continue
        if hour is None and p.isdigit() and len(p)<=2 and 0<=int(p)<=23: hour=int(p); continue
        if p and p.lower()!="exibicao": vals.append(p)
    dt=None
    if full: dt=dparse(full)
    elif date_s: y,m,dd=map(int,date_s.split("-")); dt=datetime(y,m,dd,hour or 0,tzinfo=UTC)
    return dt,phone," | ".join(vals),(full is not None)
def clean_val(v):
    if not v: return ""
    for pat,lab in [(r"codLoja=0*(\d+)","loja "),(r"codigoCliente=0*(\d+)","cliente "),
                    (r"pedidoCliente=([A-Za-z0-9\-]+)","pedido "),(r"cpfCnpj=0*(\d+)","CNPJ ")]:
        m=re.search(pat,v)
        if m: return lab+m.group(1)
    v=re.sub(r"\|\s*none\s*\|\s*200\s*\|.*$","",v).strip(" |"); v=re.sub(r"\{.*\}","",v).strip(" |")
    v=re.sub(r"^\d{1,2}\s*\|\s*","",v).strip(); return v[:90]

journeys=defaultdict(list); cat_count={}; csat=Counter(); perfil_b=Counter(); cliente_b=Counter()
for c in cats:
    items=cmd("/event-track/%s?startDate=%s&endDate=%s&$take=5000"%(urllib.parse.quote(c,safe=""),START,END),ANALYTICS).get("resource",{}).get("items",[])
    cat_count[c]=len(items)
    for it in items:
        dt,ph,val,prec=parse_action(it.get("action"))
        if ph: journeys[ph].append({"dt":dt,"cat":c,"val":clean_val(val),"raw":val,"prec":prec})
    if c=="pesquisa csat selecao":
        for it in items:
            tail=(it.get("action") or "").split("|")[-1].strip().lower()
            if tail.startswith("f"): csat["facil"]+=1
            elif tail.startswith("m"): csat["media"]+=1
            elif tail.startswith("d"): csat["dificil"]+=1
            else: csat["inatividade"]+=1
    if c=="perfil selecao":
        for it in items:
            v=(it.get("action") or "").strip().lower()
            if v.startswith("cliente"): perfil_b["cliente"]+=1
            elif "danone" in v: perfil_b["danoner"]+=1
            elif "inativ" in v: perfil_b["inativ"]+=1
            else: perfil_b["inesp"]+=1
    if c=="cliente selecao":
        for it in items:
            v=(it.get("action") or "").strip().lower()
            if "cnpj" in v: cliente_b["cnpj"]+=1
            elif "digo" in v: cliente_b["codigo"]+=1
            elif "inativ" in v: cliente_b["inativ"]+=1
            else: cliente_b["inesp"]+=1

def cc(name): return cat_count.get(name,0)

# ============ CONTATOS ============
allc={}
for skip in range(0,1000,100):
    items=cmd("/contacts?$take=100&$skip=%d"%skip,CRM).get("resource",{}).get("items",[])
    if not items: break
    for c in items: allc[c.get("identity","").split("@")[0]]=c
active_period={ph:c for ph,c in allc.items() if (lambda d: d and P0<=d<=P1)(dparse(c.get("lastMessageDate")))}

# ============ RECS (jornadas) ============
STORE_OK={"relatorio dados lojas encontrado","relatório lojas validada","API buscar loja","API buscar loja por cnpj"}
ORDER_FOUND={"API detalhes pedido"}; ORDER_NF={"pedido não encontrado dados","pedido não encontrado exibicao"}
ORDER_ANY={"API consulta pedidos","API consulta ultimo pedido","API consulta mais pedidos","API detalhes pedido"}
FINAL={"pesquisa relatorio"}; INVALID={"codigo danoner relatório inválido","Erro codigo loja exibicao","Erro codigo loja origem"}
VALID={"codigo danoner relatório válido","relatório lojas validada"}
def brf(dt): return dt.astimezone(BR).isoformat() if dt else ""
universe=set(active_period)|set(journeys); recs=[]
for ph in universe:
    evs=sorted(journeys.get(ph,[]),key=lambda e:(e["dt"] or datetime(2000,1,1,tzinfo=UTC)))
    c=active_period.get(ph) or allc.get(ph) or {}; ex=c.get("extras") or {}
    cset=set(e["cat"] for e in evs)
    inv_typed=[e["raw"] for e in evs if e["cat"] in INVALID and e["raw"]]
    f={"any":bool(evs),"store_ok":bool(cset&STORE_OK),"order_found":bool(cset&ORDER_FOUND),
       "order_nf":bool(cset&ORDER_NF),"order_any":bool(cset&ORDER_ANY),"finalized":bool(cset&FINAL),
       "invalid":bool(cset&INVALID),"valid":bool(cset&VALID)}
    if not evs:
        narr="Apareceu como ativo (trocou mensagem), mas sem passo de jornada rastreável — provavelmente só saudação e/ou atendimento humano (transbordo não grava telefone no event-track)."
    else:
        n=[]
        if f["valid"]: n.append("informou um código válido")
        if f["invalid"]:
            t="; ".join(x for x in inv_typed if not x.replace(" ","").isdigit())[:120]
            n.append("teve código recusado"+(f' (digitou: "{t}")' if t else " (código incompleto/errado)"))
        if f["store_ok"]: n.append("a loja foi localizada")
        if f["order_found"]: n.append("o pedido foi encontrado")
        elif f["order_nf"]: n.append("consultou pedido mas nada foi encontrado")
        elif f["order_any"]: n.append("consultou pedidos")
        n.append("chegou à pesquisa de satisfação (concluiu)" if f["finalized"] else "não chegou à pesquisa (provável abandono)")
        narr="Esse contato "+", ".join(n)+"."
    recs.append({"phone":ph,"name":c.get("name",""),"tipo":ex.get("tipoUsuario",""),
        "codigoLoja":ex.get("codigoLoja",""),"cnpjLoja":ex.get("cnpjLoja",""),
        "last":(c.get("lastMessageDate","") or "")[:10],"flags":f,"narr":narr,
        "first":brf(evs[0]["dt"]) if evs and evs[0]["dt"] else "",
        "events":[{"t":brf(e["dt"]),"prec":e["prec"],"cat":e["cat"],"val":e["val"]} for e in evs]})

# ============ DESK TICKETS ============
def fmt(sec):
    if sec is None: return "—"
    sec=int(round(sec)); d,r=divmod(sec,86400); h,r=divmod(r,3600); m,s=divmod(r,60)
    return (f"{d}d {h:02d}:{m:02d}:{s:02d}" if d else f"{h:02d}:{m:02d}:{s:02d}")
desk={"available":bool(TKEY)}
if TKEY:
    items=cmd("/tickets?$take=100",DESK,TKEY).get("resource",{}).get("items",[])
    per=[t for t in items if (lambda d:d and P0<=d<=P1)(dparse(t.get("storageDate")))]
    stt=Counter(t.get("status") for t in per)
    q=[];fr=[];at=[]
    byag=defaultdict(list)
    def agname(t):
        a=t.get("agentIdentity") or t.get("closedBy") or "—"
        return a.replace("%40","@").split("@")[0]
    for t in per:
        sd,od,frd,cd=dparse(t.get("storageDate")),dparse(t.get("openDate")),dparse(t.get("firstResponseDate")),dparse(t.get("closeDate"))
        if od and sd: q.append((od-sd).total_seconds())
        if frd and od: fr.append((frd-od).total_seconds())
        if cd and od: at.append((cd-od).total_seconds())
        byag[agname(t)].append(t)
    def avg(x): return sum(x)/len(x) if x else None
    def mx(x): return max(x) if x else None
    agents=[]
    for ag,ts in sorted(byag.items(),key=lambda kv:-len(kv[1])):
        if ag=="—": continue
        frs=[];ats=[]
        for t in ts:
            od,frd,cd=dparse(t.get("openDate")),dparse(t.get("firstResponseDate")),dparse(t.get("closeDate"))
            if frd and od: frs.append((frd-od).total_seconds())
            if cd and od: ats.append((cd-od).total_seconds())
        sc=Counter(t.get("status") for t in ts)
        agents.append({"name":ag,"n":len(ts),"fr":fmt(avg(frs)) if frs else "—",
                       "at":fmt(avg(ats)) if ats else "—","transferred":sc.get("Transferred",0)==len(ts)})
    desk.update({"total":len(per),"closed":stt.get("ClosedAttendant",0),"transferred":stt.get("Transferred",0),
        "waiting":stt.get("Waiting",0),"open":stt.get("Open",0),
        "lost":stt.get("ClosedClient",0)+stt.get("Canceled",0),
        "queueAvg":fmt(avg(q)),"queueMax":fmt(mx(q)),"frAvg":fmt(avg(fr)),"frMax":fmt(mx(fr)),
        "attAvg":fmt(avg(at)),"attMax":fmt(mx(at)),"agents":agents})

# ============ MONTA ONEPAGE ============
def pct(x): return round(x*100,1) if x is not None else None
sat_validas=csat["facil"]+csat["media"]+csat["dificil"]
diff=msg.get("previousPeriodDiff",{}) or {}
onepage={
 "users":{"active":act,"engaged":eng,
   "recCount":rec.get("recurrentIdentitiesCount"),"recRate":pct(rec.get("recurrentIdentitiesRate")),
   "recVar":pct(rec.get("recurrentIdentitiesCountVariation")),
   "rejection": 0.0 if (act is not None and eng is not None and act==eng) else None},
 "messages":{"total":msg.get("totalMessages"),"sent":msg.get("sentMessages"),"received":msg.get("receivedMessages"),
   "active":msg.get("activeMessages"),"sentPct":pct(msg.get("sentRate")),"receivedPct":pct(msg.get("receivedRate")),
   "totalVar":pct(diff.get("totalMessagesVariation")),"sentVar":pct(diff.get("sentMessagesVariation")),
   "receivedVar":pct(diff.get("receivedMessagesVariation")),"activeVar":pct(diff.get("activeMessagesVariation"))},
 "flow":{"retention":flow.get("usersRetention"),"retentionPct":pct(flow.get("retentionUsersRate")),
   "attendance":flow.get("usersInAttendance"),"attendancePct":pct(flow.get("attendanceUsersRate")),
   "exception":flow.get("usersInException"),"exceptionPct":pct(flow.get("exceptionUsersRate")),
   "total":flow.get("totalUsers"),
   "retentionVar":pct((flow.get("flowMetricsPreviousPeriodDiff") or {}).get("UsersRetentionVariation")),
   "attendanceVar":pct((flow.get("flowMetricsPreviousPeriodDiff") or {}).get("UsersInAttendanceVariation")),
   "exceptionVar":pct((flow.get("flowMetricsPreviousPeriodDiff") or {}).get("UsersInExceptionVariation"))},
 "blocks":[{"name":b.get("blockName"),"count":b.get("count")} for b in blocks][:10],
 "kpis":{"codValido":cc("codigo danoner relatório válido"),"codInvalido":cc("codigo danoner relatório inválido"),
   "lojasLocalizadas":cc("relatorio dados lojas encontrado"),"lojaNFcnpj":cc("loja não encontrada cnpj exibicao"),
   "lojaNFcod":cc("loja não encontrada exibicao"),"pedidosNF":cc("pedido não encontrado dados"),
   "transbInicial":cc("transbordo inicial exibicao"),"transbAtend":cc("transbordo atendimento exibicao"),
   "transbForaH":cc("transbordo fora horario exibicao"),"finalizadosBot":cc("atendimentos finalizados no chatbot exibicao"),
   "inatividade":cc("Inatividade selecao")},
 "satisfaction":{"facil":csat["facil"],"media":csat["media"],"dificil":csat["dificil"],
   "validas":sat_validas,"inatividade":csat["inatividade"]},
 "desk":desk}

funnel={
 "perfil_sel":cc("perfil selecao"),"perfil_err":cc("perfil inesperado"),
 "danoner_input":cc("codigo danoner input"),"danoner_ok":cc("relatório lojas validada"),"danoner_nf":cc("loja não encontrada exibicao"),
 "perfil_cliente":perfil_b["cliente"],"perfil_danoner":perfil_b["danoner"],"perfil_inativ":perfil_b["inativ"],"perfil_inesp":perfil_b["inesp"],
 "cliente_sel":cc("cliente selecao"),"cliente_cnpj":cliente_b["cnpj"],"cliente_codigo":cliente_b["codigo"],"cliente_inativ":cliente_b["inativ"],
 "cli_cod_input":cc("codigo cliente input"),"cli_cod_err":cc("codigo cliente inesperado"),
 "cli_cnpj_input":cc("cnpj input"),"cli_cnpj_err":cc("cnpj inesperado"),"cnpj_ok":cc("loja encontrada cnpj exibicao"),"cnpj_nf":cc("loja não encontrada cnpj exibicao"),
 "pedidos_ok":cc("status pedidos exibicao"),"pedidos_mais":cc("mais pedidos exibicao"),"pedidos_espec":cc("pedido especifico exibicao"),"pedidos_nf":cc("pedido não encontrado exibicao"),
 "transb_inicial":cc("transbordo inicial exibicao"),"transb_atend":cc("transbordo atendimento exibicao"),"transb_fora":cc("transbordo fora horario exibicao"),
 "transbordados":cc("atendimentos transbordados exibicao"),"finalizados_bot":cc("atendimentos finalizados no chatbot exibicao"),
 "csat_exib":cc("pesquisa csat exibicao"),"csat_facil":csat["facil"],"csat_media":csat["media"],"csat_dificil":csat["dificil"],"csat_inatividade":csat["inatividade"]}

json.dump({"period":{"start":START,"end":END},"ts":GEN_TS,"onepage":onepage,"funnel":funnel,"recs":recs},
          open("_snapshot.json","w",encoding="utf-8"),ensure_ascii=False)
print("OK _snapshot.json | ativos",act,"| msgs",msg.get("totalMessages"),"| recs",len(recs),
      "| desk",desk.get("total"),"| csat",dict(csat),"| periodo",START,"a",END)
