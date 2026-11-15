# SSD result contract

The public data contract is unchanged by the responsibility refactor. Domain
validation, matching and metrics live in `domain/ssd/`; application revisions
and publication in `application/ssd_revision_service.py`; persistence in
`infrastructure/ssd_repository.py`. Dataset generation is in
`analysis/ssd/pipeline.py`, document normalization in
`inputs/documents/ssd_adapter.py`, and offline HTML review in
`review/offline/ssd_review.py`. This document keeps its stable path for Skills.

All values below are JSON. Version: `ssd-case-v1`.

Case bundle: `{version, case:{id,name}, steps:[], channels:{G:{concerns:[],scenarios:[],pending:[]},E:...,GT:...}, documents:[], decisions:[], pending:[]}`.

Step: `{id, order, kind:'interaction'|'action', layer:'RR'|'SR', direction:'request'|'return', sender:{id,name,type:'human'|'service',technology?:string,external?:bool}, receiver:same, operation:{name,kinds:string[]}, data:Field[], api_id:string|null, entity_ids:string[], source_refs:Ref[], aliases?:string[], parent_id?:string|null}`. Stable ids independent of labels/order. Field: `{id,name,location,type?,required?,constraints:[{kind,value,source_refs?:Ref[]}],source_refs:Ref[]}`. May retain additional metadata.

Concern: `{id,step_id,target:'sender'|'data'|'receiver',key,label,field_id?:string|null,entity_id?:string|null,condition:string,status:'active'|'pending'|'unbound',source_refs:Ref[],rule_id?:string}`.

Scenario: `{id,concern_ids:string[],step_id,target,key,field_id?:string|null,condition,expected,source_refs:Ref[],status:'active'|'pending'|'unbound'}`. Same failure may link multiple concerns. Pending entries MUST be objects with at least `{id,condition,status:'pending',source_refs:Ref[]}`.

Document: `{id,name,role:'RR'|'SR'|'test'|'intermediate',content:string,hash?:string}`. Ref: `{document_id,start_line,end_line,quote,kind?:'origin'|'context'|'test',json_pointer?:string}`. RR/SR refs point to original markdown; test records keep real test refs distinct from requirement context.

Decision: `{id,level:'concern'|'scenario',pair:'G_E'|'GT_G'|'GT_E',left_id,right_id,status:'full'|'partial'|'none',reason,origin:'auto'|'manual'}`.

Services: `ssd_pipeline.build_cases(directory, case_ids=None)` returns list of bundles; `ssd_pipeline.generate_g(bundle)` returns G channel using steps and retained API/entity metadata only. `ssd_adapter.normalize_extracted_case` accepts extracted document artifacts. The workflow entry is `ssd_pipeline.build_from_documents`, distinct from the detailed compatibility workflow. `ssd_revision_service.publish(project,bundle)` saves machine baseline and preserves human edits; `ssd_revision_service.editor(project,case_id)` returns effective bundle plus `{revision,comparison,metrics,original_metrics,history}`. `ssd_revision_service.save_revision(project,case_id,body)` takes `{base_revision,bundle,reason?}`, validates editable bundle, computes diff over stable ids and publishes immutable revision. Read/modify/write protected by lock. `ssd_revision_service.index(project)` returns `{version,cases:[{id,name,revision,metrics,pending_count}],metrics}`.

HTTP (all under `/api/projects/{rid}`): GET `ssd-results`; GET `results/{case_id}/editor`; POST `results/{case_id}/revisions`; GET `results/{case_id}/revisions`; POST `ssd-review/summary` and `ssd-review/export` accept `{scopes?:[],case_ids?:[],anchor_ids?:[],record_ids?:[]}`; summary is read-only and export returns HTML. POST `ssd-review/preview` body `{content:string|object}` returns preview; POST `ssd-review/apply` body `{content:string|object,item_ids?:[],case_ids?:[]}` applies selected nonconflicting items after user preview.

Comparison: `{concerns:Row[],scenarios:Row[]}`; Row: `{id,step_id,target,key,field_id,cells:{G:Record[],E:Record[],GT:Record[]},status:'triple'|'pair'|'single'|'partial'|'pending'|'unmatched',reason}`. Metrics keep `missing_exception_miss_rate` and `generation_validity`, each `{value,numerator,denominator,status}`. `null` for empty denominator. Only active records count.

Active offline module `review/offline/adoption.py` provides `export_html`, `summary`, and `feedback` (preview by default, explicit `apply=True` to apply). It delegates revision operations to the application service. HTML embeds a safe JSON snapshot, relevant original documents and mutable adoption decisions/comments; downloaded HTML and JSON survive reopening. Parser never executes imported HTML. Older row-editing helpers in `ssd_review.py` remain compatibility readers.

Completeness: `{pending_records,pending_case_items,revision_issues,semantic_pairs,complete}`. The editor response includes this summary. Bundle `semantic_pending` contains `{pair,left_id,right_id,step_id}` for unresolved same-anchor scenario comparisons. It is derived from current records and decisions during validation; human decisions clear the corresponding pending pair.

Coverage metadata: new machine bundles set `coverage_policy:"coverage-any-confirmed-v2"`; absent means frozen `coverage-one-to-one-v1`. The v2 policy accepts full/partial, many-to-many edges, counting distinct covered G and distinct covered GT rather than assignments. `coverage_by_record` accompanies comparison rows. `gt_identification_run_complete:false` blocks review export until source identification runs; semantic and generation pending records remain explicit.

`operation.kinds_source` distinguishes manual/declared/inferred/semantic. `data[].contract_links` records semantic API property correspondence without inventing `api_id`. `contract_binding_pending` retains missing normal-contract mapping. `display_row_id` is optional stable presentation identity on observations; it does not establish matching. Business adoption adds GT records with `origin:"business_review"`, `source_kind:"业务审核补充"`, `adopted_from_g`, `review_comment`, empty test `source_refs` and separate `requirement_refs`.

The active offline format is `business-adoption-v2`: immutable `items` (scope, key, base_revision, bundle, G rows), export_id and exclusion counts, plus mutable decisions `{item_id,g_id,adopted:boolean,comment}`. Server-side exported context hashes and immutable revisions prevent feedback rewriting RR/SR, SSD, E or G. Legacy `ssd-review-v1` and `project-review-v1` readers remain in compatibility modules; the current HTTP adoption endpoints accept v2 only. The separate Windows review handoff keeps its existing entry.


## Current read projection and combined handoff (2026-11-15)

Current editors add read-only `review_statuses` (record ID → reason, label, eligibility, confirmed GT links) and `identification_proof`. Frozen bundle content, stored revisions and metrics are not rewritten. `coverage_by_record` uses the same statuses; full/partial GT links may refer to other display rows. Save HTTP responses include the current projection. Historical revision reads keep the stored snapshot.

`POST ssd-review/summary` takes the export selection and returns saved revisions, per-scope counts and exclusion reasons without writing an export. Existing export accepts `scopes`, `case_ids`, `anchor_ids`, `record_ids`; omitted selection means all three scopes. `business-adoption-v2` remains the format: items with zero review rows may still contain a frozen bundle for complete read-only reference. `excluded.by_scope`, item review statuses and proof are included in the immutable export hash. No additional copy of result records is created for reference rendering.

`POST ssd-review/apply` accepts exact `item_ids` in addition to the legacy `case_ids` alias. When present, item IDs take precedence and must belong to the file. Preview/apply return each scope's identity, status, conflicts and changes. The new UI defaults to all ready items, never auto-applies, and invalidates every affected result cache. Feedback may only change adoption decisions and comments; editing read-only reference is rejected. Prior v2 HTML/JSON files remain readable.

Project scope identification completion is carried through comparison. Older current snapshots can recover that flag only from a matching completed identification artifact (version, scope, documents, source records and anchors); no historical file is migrated. Unscoped business pending records do not turn a completed recognition run into an unfinished run.

Result caches are bounded and keyed by persisted file identity; atomic worker writes invalidate them. Browser requests coalesce within a project generation, and publishing/saving/feedback invalidate reads. Large responses support gzip while event streams remain uncompressed.
