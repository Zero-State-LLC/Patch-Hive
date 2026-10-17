#!/usr/bin/env python3
"""Build a deterministic acquisition coverage report without admitting cases."""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("path")
    args=ap.parse_args()
    p=Path(args.path)
    rows=[]
    if p.suffix==".jsonl":
        rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    else:
        obj=json.loads(p.read_text())
        rows=obj.get("cases", obj if isinstance(obj,list) else [])
    rights=Counter(); cohorts=Counter(); authorities=Counter(); manufacturers=Counter()
    identities=set()
    for r in rows:
        rac=r.get("rights_and_consent",{}).get("rights_status") or r.get("rights_status") or "UNSPECIFIED"
        rights[rac]+=1
        cohorts[r.get("cohort") or "UNSPECIFIED"]+=1
        authorities[r.get("source_authority") or "UNSPECIFIED"]+=1
        manufacturers[r.get("manufacturer") or "UNSPECIFIED"]+=1
        ident=r.get("expected_choice") or r.get("module_id") or r.get("record_id")
        if ident and ident!="none_of_above": identities.add(ident)
    out={
      "record_count":len(rows),
      "identity_count":len(identities),
      "rights":dict(sorted(rights.items())),
      "cohorts":dict(sorted(cohorts.items())),
      "source_authorities":dict(sorted(authorities.items())),
      "manufacturers":dict(sorted(manufacturers.items())),
      "admission_decision":"NOT_COMPUTED_BY_THIS_TOOL"
    }
    print(json.dumps(out,indent=2,sort_keys=True))
if __name__=="__main__": main()
