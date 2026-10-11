"""Deterministic one-to-one counting after complete semantic pair decisions.

No text similarity is computed. Maximise the number of identified conditions,
then minimise partial matches. Stable IDs break otherwise equal choices.
"""
from collections import deque


def assign_one_to_one(decisions):
    accepted = sorted((p for p in decisions if p['status'] in {'full', 'partial'}),
        key=lambda p: (p['checker_scenario_id'], p['generated_scenario_id']))
    keys = [(p['checker_scenario_id'], p['generated_scenario_id']) for p in accepted]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate eligible assignment pair')
    cs = sorted({k[0] for k in keys})
    gs = sorted({k[1] for k in keys})
    source, sink = ('source',), ('sink',)
    graph = {}

    def edge(a, b, cost):
        forward = [b, 1, cost, len(graph.setdefault(b, []))]
        reverse = [a, 0, -cost, len(graph.setdefault(a, []))]
        graph[a].append(forward)
        graph[b].append(reverse)
        return forward

    for cid in cs:
        edge(source, ('c', cid), 0)
    references = {}
    for pair in accepted:
        key = pair['checker_scenario_id'], pair['generated_scenario_id']
        references[key] = edge(('c', key[0]), ('g', key[1]), int(pair['status'] == 'partial'))
    for gid in gs:
        edge(('g', gid), sink, 0)
    # Successive shortest residual paths yield maximum cardinality and minimum
    # partial cost. Re-routing prevents a greedy choice stealing another C's
    # only concrete candidate. Every augment adds exactly one unique C/G pair.
    while source in graph:
        distance, previous = {source: 0}, {}
        queue, queued = deque([source]), {source}
        while queue:
            a = queue.popleft()
            queued.remove(a)
            for i, e in enumerate(graph[a]):
                b, capacity, cost, _ = e
                candidate = distance[a] + cost
                if capacity and (b not in distance or candidate < distance[b]):
                    distance[b], previous[b] = candidate, (a, i)
                    if b not in queued:
                        queue.append(b)
                        queued.add(b)
        if sink not in previous:
            break
        b = sink
        while b != source:
            a, i = previous[b]
            e = graph[a][i]
            e[1] -= 1
            graph[b][e[3]][1] += 1
            b = a
    selected = [p for p in accepted if references[(p['checker_scenario_id'], p['generated_scenario_id'])][1] == 0]
    selected_keys = {(p['checker_scenario_id'], p['generated_scenario_id']) for p in selected}
    return {'method': 'maximum_cardinality_then_full_one_to_one',
        'selected_pairs': selected,
        'eligible_but_unselected_pairs': [p for p in accepted if (p['checker_scenario_id'], p['generated_scenario_id']) not in selected_keys],
        'full_count': sum(p['status'] == 'full' for p in selected),
        'partial_count': sum(p['status'] == 'partial' for p in selected)}
