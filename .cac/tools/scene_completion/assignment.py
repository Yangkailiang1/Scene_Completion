"""Maximum-cardinality semantic matching: only confirmed complete pairs score."""
def full_assignment(decisions,left_ids=None,right_ids=None):
    graph={}
    for d in decisions:
        if d['status']=='full' and (left_ids is None or d['left_id'] in left_ids) and (right_ids is None or d['right_id'] in right_ids):
            graph.setdefault(d['left_id'],set()).add(d['right_id'])
    assigned={}
    def visit(left,seen):
        for right in sorted(graph.get(left,())):
            if right in seen:continue
            seen.add(right)
            if right not in assigned or visit(assigned[right],seen):assigned[right]=left;return True
        return False
    for left in sorted(graph):visit(left,set())
    return [{'checker_scenario_id':left,'generated_scenario_id':right,'status':'full'} for right,left in sorted(assigned.items())]
