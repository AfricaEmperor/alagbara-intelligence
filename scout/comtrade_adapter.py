from __future__ import annotations
import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"

def fetch_comtrade(*, reporter_code=204, period=2024, cmd_code="2501",
                   flow_code="M", partner_code=0, partner2_code=0, max_records=500):
    params={"reporterCode":reporter_code,"period":period,"cmdCode":cmd_code,
            "flowCode":flow_code,"partnerCode":partner_code,"partner2Code":partner2_code,
            "maxRecords":max_records}
    url=BASE_URL+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"ALAGBARA-SCOUT-WEB-02C/0.1"})
    with urllib.request.urlopen(req,timeout=30) as response:
        return json.load(response)

def acquire(out_path="data/raw/comtrade_ben_2501_2024.json"):
    payload=fetch_comtrade(
        reporter_code=int(os.getenv("COMTRADE_REPORTER","204")),
        period=int(os.getenv("COMTRADE_PERIOD","2024")),
        cmd_code=os.getenv("COMTRADE_HS","2501"),
        flow_code=os.getenv("COMTRADE_FLOW","M"))
    p=Path(out_path); p.parent.mkdir(parents=True,exist_ok=True)
    envelope={"acquired_at":datetime.now(timezone.utc).isoformat(),
              "source":"UN Comtrade","source_url":BASE_URL,
              "query":{"reporter":reporter_code,"period":period,"hs":cmd_code,"flow":flow_code,"partner":partner_code,"partner2":partner2_code},
              "payload":payload}
    p.write_text(json.dumps(envelope,indent=2),encoding="utf-8")
    return p

if __name__=="__main__":
    print(acquire())
