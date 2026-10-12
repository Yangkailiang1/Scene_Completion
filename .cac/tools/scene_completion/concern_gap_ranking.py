"""Same-concern historical cosine sums, category TopN and seeded fallback."""
import math
import random
from .sources import fingerprint


def scene_text(unit):
    return '\n'.join(str(unit.get(k, '')) for k in
        ('exception_object', 'operation', 'failure_mechanism', 'trigger_condition')) + '\n' + '\n'.join(unit.get('necessary_conditions', []))


def cosine(a, b):
    if len(a) != len(b) or not a or any(not math.isfinite(v) for v in a+b):
        raise ValueError('invalid embedding dimensions or values')
    x, y = sum(v*v for v in a), sum(v*v for v in b)
    if not x or not y: raise ValueError('zero embedding vector')
    return sum(v*w for v,w in zip(a,b)) / math.sqrt(x*y)


def rank(candidates, history, client, seed=42):
    if type(seed) is not int: raise ValueError('recommendation seed must be an integer')
    if len({u['scenario_id'] for u in candidates}) != len(candidates):
        raise ValueError('duplicate recommendation candidates')
    history = [u for u in history if u['mapping_status']=='mapped']
    # GT is intentionally not an argument to this function.
    texts = {u['scenario_id']: scene_text(u) for u in candidates+history}
    applicable = {k for u in candidates for k in u['concern_keys'] if any(k in h['concern_keys'] for h in history)}
    vector_ids = sorted({u['scenario_id'] for u in candidates+history if set(u['concern_keys']) & applicable})
    values = client.embeddings([texts[k] for k in vector_ids])
    if len(values) != len(vector_ids): raise ValueError('incomplete embedding set')
    vectors = dict(zip(vector_ids, values))
    categories, selected = [], set()
    for key in sorted({k for u in candidates for k in u['concern_keys']}):
        peers = sorted([u for u in candidates if key in u['concern_keys']],key=lambda u:u['scenario_id'])
        old = sorted([h for h in history if key in h['concern_keys']],key=lambda h:h['scenario_id'])
        n = len(peers)
        count = min(n, max(10, math.ceil(n*.1))) if old else min(n, 10)
        rows=[]
        if old:
            for u in peers:
                details = [{'history_id':h['scenario_id'],'cosine':cosine(vectors[u['scenario_id']],vectors[h['scenario_id']])} for h in old]
                rows.append({'scenario_id':u['scenario_id'],'score':sum(d['cosine'] for d in details),'similarities':details})
            rows.sort(key=lambda r:(-r['score'],r['scenario_id']))
            chosen={r['scenario_id'] for r in rows[:count]}
            method='raw_cosine_sum_top_n'
        else:
            generator=random.Random(int(fingerprint([seed,key])[:16],16))
            chosen={u['scenario_id'] for u in generator.sample(peers,count)}
            rows=[{'scenario_id':u['scenario_id'],'score':None,'similarities':[]} for u in peers]
            method='seeded_random_no_history'
        for i,r in enumerate(rows,1):
            r.update(rank=i if old else None,selected=r['scenario_id'] in chosen,selection_reason=method)
        selected |= chosen
        categories.append({'concern_key':key,'candidate_count':n,'history_count':len(old),
            'selected_count':count,'method':method,'items':rows})
    return {'complete':True,'model':client.model('embedding'),'seed':seed,
        'history_hash':fingerprint(history),'candidate_hash':fingerprint(candidates),
        'text_hashes':{k:fingerprint(texts[k]) for k in sorted(texts)},
        'categories':categories,'selected_ids':sorted(selected),
        'vectors':{k:vectors[k] for k in vector_ids},'rerank':False}
