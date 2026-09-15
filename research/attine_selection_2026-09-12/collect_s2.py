"""Reproducible public Semantic Scholar discovery; no credentials required."""
import json, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
RAW.mkdir(exist_ok=True)
QUERIES = [
 '("leaf-cutting ants" | "leafcutting ants" | "leaf-cutter ants" | "leaf cutting ants") + (plant | substrate | diet | food | foraging | selection | rejection | avoidance)',
 'Acromyrmex + (plant | diet | selection | preference | foraging | rejection | substrate)',
 '("Atta cephalotes" | "Atta colombica" | "Atta sexdens" | "Atta texana" | "Atta laevigata" | "Atta mexicana" | "Atta insularis") + (plant | diet | selection | preference | foraging | rejection)',
 '("Atta capiguara" | "Atta bisphaerica" | "Atta vollenweideri" | "Atta opaciceps" | Amoimyrmex) + (plant | diet | selection | preference | foraging | grass)',
 '"formigas cortadeiras" + (seleção | preferência | forrageamento | vegetal | plantas)',
 '"hormigas cortadoras" + (selección | preferencia | forrajeo | plantas)',
 '(Blattschneiderameisen | "fourmis champignonnistes" | "fourmis attines") + (Pflanzen | choix | substrat | Futterwahl | Pflanzenwahl)',
 '(Trachymyrmex | Mycetomoellerius | Paratrachymyrmex | Sericomyrmex | Cyphomyrmex | Mycocepurus | Mycetarotes | Mycetophylax | Apterostigma) + (foraging | substrate | plant | diet | preference)',
 '(Leucoagaricus | Leucocoprinus | Attamyces) + (plant | extract | alkaloid | lignan | coumarin | phytochemical | óleo | extrato | vegetal)',
 '("formigas cortadeiras" | "hormigas cortadoras" | "leaf-cutting ants") + (tese | thesis | dissertation | dissertação | tesis | rapport | report)',
]
FIELDS='title,authors,year,externalIds,url,openAccessPdf,abstract,publicationTypes,venue,publicationDate'
all_papers={}
log=[]
for i,q in enumerate(QUERIES):
    token=None
    page=0
    while True:
        page+=1
        path=RAW/f's2_query_{i+1:02d}_page_{page:02d}.json'
        params={'query':q,'fields':FIELDS}
        if token: params['token']=token
        url='https://api.semanticscholar.org/graph/v1/paper/search/bulk?'+urllib.parse.urlencode(params)
        try:
            if path.exists():
                d=json.loads(path.read_text())
            else:
                for attempt in range(4):
                    try:
                        with urllib.request.urlopen(url,timeout=45) as response: d=json.load(response)
                        break
                    except urllib.error.HTTPError as exc:
                        if exc.code!=429 or attempt==3: raise
                        time.sleep([3,10,30][attempt])
                path.write_text(json.dumps(d,ensure_ascii=False,indent=2))
            log.append({'query_id':i+1,'query':q,'page':page,'total':d.get('total'),'returned':len(d.get('data',[])),'url':url})
            for p in d.get('data',[]):
                pid=p['paperId']
                if pid not in all_papers: all_papers[pid]={**p,'query_ids':[]}
                if i+1 not in all_papers[pid]['query_ids']: all_papers[pid]['query_ids'].append(i+1)
            print(json.dumps({'query':i+1,'page':page,'total':d.get('total'),'unique_so_far':len(all_papers)}),flush=True)
            token=d.get('token')
            if not token: break
            time.sleep(1.2)
        except Exception as exc:
            log.append({'query_id':i+1,'query':q,'error':str(exc)})
            print(json.dumps(log[-1]),flush=True)
            break
    time.sleep(1.2)
(ROOT/'s2_search_log.json').write_text(json.dumps(log,ensure_ascii=False,indent=2))
(ROOT/'s2_candidates.json').write_text(json.dumps(list(all_papers.values()),ensure_ascii=False,indent=2))
print('Saved',len(all_papers),'unique discovery records.',flush=True)
