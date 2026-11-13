"""Choose the supported case workflow without coupling SSD rules to detailed DAGs."""


def _build_cases(
    ex,
    rr,
    sr,
    tests,
    catalogue,
    groups,
    extraction_truth,
    adjudications,
    test_catalogue=None,
    test_alignment=None,
    ar=None,
    *,
    supplied=None,
    reference_groups=None,
):
    from scene_completion.workflow.ssd_pipeline import build_from_documents, enabled

    if enabled(ex):
        return build_from_documents(
            ex, rr, sr, tests, catalogue, groups, test_catalogue, test_alignment
        )
    from scene_completion.compat.detailed.case_pipeline import _build_cases as build_detailed

    return build_detailed(
        ex,
        rr,
        sr,
        tests,
        catalogue,
        groups,
        extraction_truth,
        adjudications,
        test_catalogue,
        test_alignment,
        ar,
        supplied=supplied,
        reference_groups=reference_groups,
    )
