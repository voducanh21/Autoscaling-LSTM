#!/usr/bin/env python3
import csv, os
BASE=os.getenv("BASELINE","cost_requests_summary_baseline_hpa.csv")
PRO=os.getenv("PROACTIVE","cost_requests_summary_proactive.csv")
TH=float(os.getenv("THRESHOLD_PCT","15"))
def read(p):
  m={}
  with open(p,"r",encoding="utf-8") as f:
    r=csv.DictReader(f)
    for row in r:
      svc=row["service"]
      def num(k):
        v=row.get(k)
        if v in (None,"","None"): return None
        try: return float(v)
        except: return None
      m[svc]={
        "cpu": num("total_cpu_requests_seconds"),
        "mem": num("total_mem_requests_seconds"),
      }
  return m
def pct(b,p):
  if b is None or p is None or b==0: return None
  return (p/b-1.0)*100.0
b=read(BASE); p=read(PRO)
svcs=sorted(set(b.keys())|set(p.keys()))
print("service,cpu_increase_pct,mem_increase_pct,cpu_pass,mem_pass")
for s in svcs:
  bc=b.get(s,{}).get("cpu"); pc=p.get(s,{}).get("cpu")
  bm=b.get(s,{}).get("mem"); pm=p.get(s,{}).get("mem")
  dc=pct(bc,pc); dm=pct(bm,pm)
  cpu_pass = (dc is not None and dc <= TH)
  mem_pass = (dm is not None and dm <= TH)
  print(f"{s},{dc},{dm},{cpu_pass},{mem_pass}")
