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

HTTP (all under `/api/projects/{rid}`): GET `ssd-results`; GET `results/{case_id}/editor`; POST `results/{case_id}/revisions`; GET `results/{case_id}/revisions`; POST `ssd-review/export` body `{case_ids?:[],record_ids?:[]}` returns HTML; POST `ssd-review/preview` body `{content:string|object}` returns preview; POST `ssd-review/apply` body `{content:string|object,case_ids?:[]}` applies only selected nonconflicting cases after user preview.

Comparison: `{concerns:Row[],scenarios:Row[]}`; Row: `{id,step_id,target,key,field_id,cells:{G:Record[],E:Record[],GT:Record[]},status:'triple'|'pair'|'single'|'partial'|'pending'|'unmatched',reason}`. Metrics keep `missing_exception_miss_rate` and `generation_validity`, each `{value,numerator,denominator,status}`. `null` for empty denominator. Only active records count.

Offline module public functions: `export_html(project,body)->str`, `preview_feedback(project,content)->dict`, `apply_feedback(project,content,case_ids=None)->dict`. It delegates revision operations to the application service. HTML embeds safe JSON snapshot, relevant original documents and editable rows; downloaded revised HTML and JSON must survive reopening; parser never executes imported HTML.

Completeness: `{pending_records,pending_case_items,revision_issues,semantic_pairs,complete}`. The editor response includes this summary. Bundle `semantic_pending` contains `{pair,left_id,right_id,step_id}` for unresolved same-anchor scenario comparisons. It is derived from current records and decisions during validation; human decisions clear the corresponding pending pair.
