"""Code-agent friendly client of the same local workbench API; JSON/JSONL only."""
import argparse,json,sys,time,urllib.request,urllib.error,urllib.parse,base64,getpass
from pathlib import Path

class API:
    def __init__(self,server):
        p=urllib.parse.urlsplit(server)
        if p.scheme not in ('http','https') or p.username or p.password or p.query or p.fragment or p.hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('CLI仅连接本机工作台；请使用http://127.0.0.1:8765')
        self.server=server.rstrip('/')
    def call(self,path,body=None,method=None):
        request=urllib.request.Request(self.server+'/api/'+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=60) as r:return json.load(r)
        except urllib.error.HTTPError as e:
            try:detail=json.loads(e.read()).get('detail','操作失败')
            except (ValueError,AttributeError):detail='操作失败'
            raise ValueError(f'工作台HTTP {e.code}: {detail}') from None
        except urllib.error.URLError:raise ValueError('无法连接本机工作台，请先启动serve.py并保持运行') from None
    def download(self,path,target,body=None):
        req=urllib.request.Request(self.server+'/api/'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=600) as r:
                with Path(target).open('wb') as out:
                    import shutil
                    shutil.copyfileobj(r,out)
        except urllib.error.HTTPError as e:
            raise ValueError('下载失败：'+e.read().decode('utf8',errors='replace')[:2000]) from None
        return {'saved_to':str(Path(target).resolve()),'bytes':Path(target).stat().st_size}


def capabilities():
    command_actions=next(a for a in parser()._actions if isinstance(a,argparse._SubParsersAction))
    parameters={name:[{'flags':a.option_strings or [a.dest],'required':a.required,'type':getattr(a.type,'__name__','boolean' if isinstance(a,(argparse._StoreTrueAction,argparse._StoreFalseAction)) else 'string'),'choices':list(a.choices) if a.choices is not None else None,'help':a.help} for a in command._actions if a.dest!='help'] for name,command in command_actions.choices.items()}
    return {'version':'business-review-v1','format':'JSON/JSONL','command_parameters':parameters,'commands':{
      'projects/create':'项目列表、新建项目和Markdown/XLSX输入；共享网页数据目录',
      'accounts/save-account':'每Key模型允许列表；expected_revision校验、环境变量引用、隐藏输入及--dry-run',
      'configure':'模型、路由、思考、输出/上下文预算、吞吐监视及候选切换；--config-file及--dry-run',
      'pending':'--project ID [--item ID --file answer.json --dry-run]；问题与回答历史，保存不执行模型',
      'sources':'--project ID [--source ID --start N --end N]；原文及行号',
      'registry':'--project ID [--file registry.json --dry-run]；expected_hash必填',
      'patterns':'--project ID [--file settings.json --dry-run]；expected_version必填',
      'reviews':'--project ID --node ID [--file decision.json --dry-run]；revision/input_hash必填',
      'test-sources':'--project ID [--file sources.json --dry-run]；expected_version必填',
      'recommendations':'--project ID --case ID [--file feedback.json --dry-run]；revision/settings_hash必填',
      'handoff':'--project ID --out FILE.zip [--format windows|project] [--dry-run]',
      'feedback':'--project ID --out FILE.json 导出；--file FILE.json [--dry-run] 导入预览/应用；不自动重跑',
      'impact':'--project ID；输出plan_id、来源节点及真实DAG下游',
      'rerun':'--project ID --affected --plan-id ID [--dry-run]；或--node ID定向重跑',
      'repair-export/repair-submit':'外部Code Agent修复必须通过原校验器',
      'input-scan':'--project ID --directory PATH [--watch|--no-watch]；服务端稳定采样与监控目录，CLI退出后继续',
      'imports':'--project ID [--item ID --file decision.json --dry-run]；导入预览、确认、原文件及转换结果',
      'recovery':'--project ID [--file policy.json --dry-run]；版本化恢复策略及持久预算记录',
      'run/status/events/artifacts/guide/answer':'run支持--case（只跑所选）、--all-cases、--priority-case（优先后继续）；answer仅保存'},
      'input_structures':{
        'pending':{'revision':'当前单问题revision','reviewer':'审核人','choice':'按question_choices选择','answer':'规则、触发条件或决定及依据','concern_key':'仅确认异常时必填'},
        'registry':{'expected_hash':'registry.current_hash','registry':'完整定义对象'},
        'patterns':{'expected_version':'patterns.version','settings':'完整项目设置'},
        'reviews':{'input_hash':'当前预览输入哈希','action':'approve/reject/regenerate','note':'审核说明'},
        'recommendations':{'revision':'feedback_revision','settings_hash':'冻结推荐版本','scenario_id':'Q中的场景ID','choice':'adopt/not_applicable/not_needed/already_covered/defer/withdraw','reviewer':'审核人','note':'决定依据','truth_resolution':'可选 {choice:new} 或 {choice:link,truth_id:现有候选ID}'},
        'feedback':'审核包导出的完整JSON；默认先--dry-run预览，使用--allow-partial显式保留冲突',
        'imports':{'expected_revision':'文件revision','artifact_id':'目标产物ID','action':'accept/reject/retry_conversion/accept_source','case_id':'可选已确认组ID','replace':'显式替换既有成功版本','payload':'可选编辑后的本任务JSON'},
        'recovery':{'expected_revision':'策略revision','settings':{'enabled':True,'max_node_calls':2,'max_run_calls':20,'allowed_submission_modes':['tool_calls','json_text'],'max_output_tokens':'可选项目明确允许的恢复上限'}},
        'test-sources':{'expected_version':'当前测试源版本','sources':'文件内容/编码列表'}},
      'answer_fields':['revision','choice','answer','reviewer','concern_key(异常判定时)'],
      'question_choices':{k:v['choices'] for k,v in __import__('scene_completion.review_questions',fromlist=['TYPES']).TYPES.items()},
      'rules':['所有写入共用网页校验及版本记录','审核包禁止模型执行及配置变更','不重置账本，不直接覆盖正式产物']}

def output(value):print(json.dumps(value,ensure_ascii=False),flush=True)

def parser():
    p=argparse.ArgumentParser(description='让Code Agent操作同一网页工作台；输出JSON或JSONL，不另建隐藏运行目录。');p.add_argument('--server',default='http://127.0.0.1:8765');sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('capabilities');sub.add_parser('projects');create=sub.add_parser('create');create.add_argument('--name',required=True)
    for role in ('rr','sr','test'):create.add_argument('--'+role,action='append',default=[])
    create.add_argument('--input-dir',help='自动分配明确命名的RR/SR/测试文件，其他文件进入同事产物导入')
    create.add_argument('--mode',choices=('manual','auto'),default='manual');create.add_argument('--case',action='append',default=[])
    accounts=sub.add_parser('accounts')
    save=sub.add_parser('save-account');save.add_argument('--id');save.add_argument('--dry-run',action='store_true');save.add_argument('--name',required=True);save.add_argument('--base-url',required=True);save.add_argument('--model',action='append',required=True);group=save.add_mutually_exclusive_group();group.add_argument('--api-key-env');group.add_argument('--prompt-key',action='store_true',help='终端隐藏输入API Key；密钥不进入命令历史')
    for cmd in ('status','artifacts','run','events','configure','config','diagnose','repair-export','repair-submit','rerun','guide','answer'):
        a=sub.add_parser(cmd);a.add_argument('--project',required=True)
        if cmd=='run':
            a.add_argument('--wait',action='store_true');a.add_argument('--mode',choices=('manual','auto'));a.add_argument('--timeout',type=float,default=3600);a.add_argument('--poll',type=float,default=2)
            scope=a.add_mutually_exclusive_group();scope.add_argument('--case',action='append');scope.add_argument('--all-cases',action='store_true');a.add_argument('--priority-case',action='append')
        if cmd=='events':a.add_argument('--after',type=int,default=0);a.add_argument('--node');a.add_argument('--limit',type=int,default=200)
        if cmd in ('config','diagnose'):
            a.add_argument('--node');a.add_argument('--task',default='agent');a.add_argument('--limit',type=int,default=20)
        if cmd in ('repair-export','repair-submit'):
            a.add_argument('--node',required=True)
            if cmd=='repair-export':a.add_argument('--out',required=True)
            else:a.add_argument('--file',required=True);a.add_argument('--validate-only',action='store_true')
        if cmd=='rerun':
            g=a.add_mutually_exclusive_group(required=True);g.add_argument('--node');g.add_argument('--affected',action='store_true');a.add_argument('--plan-id');a.add_argument('--dry-run',action='store_true');a.add_argument('--text',default='按已更新的模型配置重新执行当前节点')
        if cmd=='configure':
            a.add_argument('--account');a.add_argument('--model');a.add_argument('--concurrency',type=int);a.add_argument('--config-file',help='运行参数JSON，不接受凭证或配额账本修改');a.add_argument('--preset',choices=('deepseek-thinking',));a.add_argument('--dry-run',action='store_true')
            for flag,key in [('max-output-tokens','max_tokens'),('max-context-tokens','max_context_tokens'),('connect-timeout','timeout_seconds'),('idle-timeout','stream_idle_timeout_seconds'),('total-timeout','stream_total_timeout_seconds'),('max-model-calls','agent_max_model_calls')]:a.add_argument(*(['--max-output-tokens','--max-tokens','--maxtokens'] if flag=='max-output-tokens' else ['--'+flag]),dest=key,type=int)
            a.add_argument('--auto-switch',action=argparse.BooleanOptionalAction,default=None,help='按显式候选列表自动切换，下一请求生效')
            a.add_argument('--fallback-model',action='append',help='同账号候选模型，按顺序；完整配置可用--config-file')
            a.add_argument('--min-throughput',type=float,help='UTF-8字节/4估算Token每秒阈值，非账单Token')
            a.add_argument('--throughput-window',type=int);a.add_argument('--throughput-grace',type=int);a.add_argument('--stall-timeout',type=int)
            a.add_argument('--thinking',choices=('auto','on','off'));a.add_argument('--thinking-api',choices=('legacy','enable_thinking','chat_template_kwargs','omit'));a.add_argument('--reasoning-effort');a.add_argument('--thinking-budget',type=int)
            a.add_argument('--submission-mode',choices=('tool_calls','json_text'));a.add_argument('--max-tokens-parameter',choices=('max_tokens','max_completion_tokens'));a.add_argument('--stage-output',action='append',default=[],metavar='TASK=TOKENS')
            for flag in ('stream','stream-usage','send-reasoning-effort','supports-tool-choice','supports-parallel-tool-calls','reasoning-replay','json-response-format','stream-reasoning','supplement-tests'):a.add_argument(*(['--stream-reasoning','--show-reasoning'] if flag=='stream-reasoning' else ['--'+flag]),action=argparse.BooleanOptionalAction,default=None)

        if cmd in ('guide','answer'):a.add_argument('--node',required=True);a.add_argument('--text',required=True);a.add_argument('--dry-run',action='store_true')
        if cmd=='answer':a.add_argument('--question',required=True)
    for cmd in ('pending','sources','registry','patterns','reviews','recommendations','handoff','feedback','impact','test-sources','imports','input-scan','recovery'):
        a=sub.add_parser(cmd);a.add_argument('--project',required=True);a.add_argument('--file');a.add_argument('--out');a.add_argument('--dry-run',action='store_true');a.add_argument('--item');a.add_argument('--node');a.add_argument('--case');a.add_argument('--source');a.add_argument('--start',type=int,default=1);a.add_argument('--end',type=int);a.add_argument('--format',choices=('windows','project'),default='windows');a.add_argument('--allow-partial',action='store_true')
        if cmd=='input-scan':a.add_argument('--directory');a.add_argument('--watch',action=argparse.BooleanOptionalAction,default=None)
    return p

def main(argv=None,client=None):
    args=parser().parse_args(argv);api=client or API(args.server)
    if args.command=='capabilities':output(capabilities());return 0
    if args.command=='projects':output(api.call('projects'));return 0
    if args.command=='accounts':output(api.call('model-accounts'));return 0
    if args.command=='save-account':
        accounts=api.call('model-accounts');body={'expected_revision':accounts['revision'],'name':args.name,'base_url':args.base_url,'models':args.model,'dry_run':args.dry_run}
        if args.id:body['id']=args.id
        if args.api_key_env:body['api_key_env']=args.api_key_env
        if args.prompt_key:body['api_key']=getpass.getpass('API Key（隐藏输入）: ')
        output(api.call('model-accounts',body,'PUT'));return 0
    if args.command=='create':
        other=[]
        if args.input_dir:
            from .artifact_imports import role_hint
            directory=Path(args.input_dir).resolve()
            if not directory.is_dir():raise ValueError('input目录不存在')
            for file in directory.iterdir():
                if not file.is_file() or file.is_symlink() or file.name.startswith('.') or file.suffix.lower() not in {'.md','.markdown','.json','.xlsx'}:continue
                role=role_hint(file.name,file.read_text(encoding='utf-8-sig') if file.suffix.lower()!='.xlsx' else '')
                if role in {'RR','SR','test'}:getattr(args,role.lower()).append(str(file))
                else:other.append(file)
        sources={}
        for role in ('rr','sr','test'):
            sources['test' if role=='test' else role.upper()]=[]
            for name in getattr(args,role):
                file=Path(name);row={'name':file.name}
                if file.suffix.lower()=='.xlsx' and role=='test':row['content_base64']=base64.b64encode(file.read_bytes()).decode()
                else:row['content']=file.read_text(encoding='utf-8-sig')
                sources['test' if role=='test' else role.upper()].append(row)
        value=api.call('projects',{'name':args.name,'sources':sources,'review_mode':args.mode,'case_ids':args.case})
        if args.input_dir:api.call('projects/'+value['id']+'/input-scan',{'directory':str(Path(args.input_dir).resolve()),'watch':True})
        output(value);return 0
    rid=args.project
    if len(rid)!=32 or any(c not in '0123456789abcdef' for c in rid):raise ValueError('项目ID必须是工作台返回的32位ID')
    path='projects/'+rid
    if args.command=='repair-export':
        value=api.call(path+'/node-repair?'+urllib.parse.urlencode({'task_key':args.node}));target=Path(args.out);target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');output({'saved_to':str(target),'task_key':args.node,'note':'包含本节点业务材料，保留本地，不提交Git'});return 0
    if args.command=='repair-submit':
        value=json.loads(Path(args.file).read_text(encoding='utf-8-sig'));output(api.call(path+'/node-repair',{'task_key':args.node,'repair':value,'validate_only':args.validate_only}));return 0
    if args.command in ('config','diagnose'):
        query=urllib.parse.urlencode({**({'task_key':args.node} if args.node else {'task':args.task}),**({'limit':args.limit} if args.command=='diagnose' else {})})
        output(api.call(path+('/diagnostics' if args.command=='diagnose' else '/config')+'?'+query));return 0
    if args.command=='rerun':
        if args.affected:
            if not args.plan_id:raise ValueError('先impact查看影响范围，再传--plan-id')
            output(api.call(path+'/rerun-affected',{'plan_id':args.plan_id,'dry_run':args.dry_run}));return 0
        if args.dry_run:output({'valid':True,'saved':False,'node':args.node,'note':'单节点状态详见diagnose；不启动执行'});return 0
        output(api.call(path+'/rerun-node',{'task_key':args.node,'text':args.text,'dry_run':args.dry_run}));return 0
    if args.command in {'pending','sources','registry','patterns','reviews','recommendations','handoff','feedback','impact','test-sources','imports','input-scan','recovery'}:
        body=json.loads(Path(args.file).read_text(encoding='utf-8-sig')) if args.file else None
        if body is not None and not isinstance(body,dict):raise ValueError('输入文件必须为JSON对象')
        if body is not None:body={**body,'dry_run':args.dry_run,'via':'cli'}
        cmd=args.command
        if cmd=='input-scan':
            if args.directory or args.watch is not None:
                body={**(body or {}),'dry_run':args.dry_run}
                if args.directory:body['directory']=str(Path(args.directory).resolve())
                if args.watch is not None:body['watch']=args.watch
            output(api.call(path+'/input-scan',body));return 0
        if cmd=='imports':
            if body is not None and not args.item:raise ValueError('确认导入需要--item FILE_ID')
            suffix='imports/'+args.item if body is not None else 'imports'+('?item='+urllib.parse.quote(args.item,safe='') if args.item else '')
            output(api.call(path+'/'+suffix,body,'PUT' if body is not None else None));return 0
        if cmd=='handoff':
            if args.dry_run:output(api.call(path+'/handoff/export',{'format':args.format,'dry_run':True}));return 0
            if not args.out:raise ValueError('handoff需要--out')
            output(api.download(path+'/handoff/export',args.out,{'format':args.format}));return 0
        if cmd=='feedback':
            if body is not None:
                original={k:v for k,v in body.items() if k not in {'dry_run','via'}}
                output(api.call(path+'/feedback/import',{'feedback':original,'dry_run':args.dry_run,'allow_partial':args.allow_partial}));return 0
            if not args.out:raise ValueError('导出反馈需要--out，导入需要--file')
            output(api.download(path+'/feedback/export',args.out));return 0
        suffix=cmd
        if cmd=='sources' and args.source:suffix+='/'+urllib.parse.quote(args.source,safe='')+'?'+urllib.parse.urlencode({'start':args.start,**({'end':args.end} if args.end else {})})
        if cmd=='pending':
            if body is not None and not args.item:raise ValueError('回答需要--item')
            suffix+='/'+args.item if body is not None else ('/'+args.item+'/history' if args.item else '?queue=all&status=all')
        if cmd=='reviews':
            if not args.node:raise ValueError('reviews需要--node')
            suffix='decision' if body is not None else 'reviews/'+urllib.parse.quote(args.node,safe='')
            if body is not None:body={**body,'key':args.node}
        if cmd=='recommendations':
            if not args.case:raise ValueError('recommendations需要--case')
            suffix='recommendations/feedback' if body is not None else 'recommendations?test_set=business&case='+urllib.parse.quote(args.case,safe='')
            if body is not None:body={**body,'case_id':args.case}
        value=api.call(path+'/'+suffix,body,'PUT' if body is not None and cmd in {'registry','patterns','test-sources','recovery'} else None)
        if args.out:Path(args.out).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');output({'saved_to':str(Path(args.out).resolve())})
        else:output(value)
        return 0
    if args.command=='configure':
        from .runtime_settings import KEYS,validate_options,PRESETS
        body=json.loads(Path(args.config_file).read_text(encoding='utf-8-sig')) if args.config_file else {}
        if not isinstance(body,dict) or set(body)-KEYS:raise ValueError('配置文件只接受运行参数；凭证用save-account，配额账本保持不变')
        if args.preset:body={**PRESETS[args.preset],**body};body['preset']=args.preset
        for arg,key in [('account','model_account_id'),('model','agent_model'),('concurrency','max_concurrency')]+[(k,k) for k in KEYS if k not in {'thinking','stage_max_tokens','extra_body','stage_extra_body','task_models','role_models','model_profiles'}]:
            v=getattr(args,arg,None)
            if v is not None:body[key]=v
        options={'enabled':args.auto_switch,'min_tokens_per_second':args.min_throughput,'window_seconds':args.throughput_window,'grace_seconds':args.throughput_grace,'no_output_seconds':args.stall_timeout}
        if args.fallback_model is not None:options['candidates']=[{'model':m} for m in args.fallback_model]
        if any(v is not None for v in options.values()):
            current=api.call(path+'/config')['settings'].get('resilience',{})
            body['resilience']={**current,**body.get('resilience',{}),**{k:v for k,v in options.items() if v is not None}}
        if args.thinking:body['thinking']={'auto':None,'on':True,'off':False}[args.thinking]
        if 'thinking' in body:body['thinking_override']=body['thinking']
        if args.reasoning_effort is not None:body['send_reasoning_effort']=args.reasoning_effort!='omit';body['reasoning_effort']=args.reasoning_effort if args.reasoning_effort!='omit' else 'high'
        if args.stage_output:
            rules=dict(body.get('stage_max_tokens',{}))
            for item in args.stage_output:
                k,sep,v=item.partition('=')
                if not sep or not k or not v.isdecimal():raise ValueError('--stage-output格式为TASK=TOKENS')
                rules[k]=int(v)
            body['stage_max_tokens']=rules
        if not body:output(api.call(path+'/config'));return 0
        if args.dry_run:
            current=api.call(path+'/config')['settings'];merged={**current,**{k:v for k,v in body.items() if k!='preset'}}
            validate_options(merged);output({'dry_run':True,'changes':body,'notes':['仅校验参数，不保存、不调用模型；完整账号/路由及真实请求预算由服务端保存/执行时再次校验。']});return 0
        output(api.call(path+'/config',body,'PUT'));return 0

    if args.command=='guide':output(api.call(path+'/conversation',{'task_key':args.node,'text':args.text,'dry_run':args.dry_run}));return 0
    if args.command=='answer':output(api.call(path+'/answer',{'task_key':args.node,'question_id':args.question,'text':args.text,'dry_run':args.dry_run}));return 0
    if args.command=='events':
        query=urllib.parse.urlencode({'after':args.after,'limit':args.limit,**({'task_key':args.node} if args.node else {})});output(api.call(path+'/events/history?'+query));return 0
    if args.command=='status':output(api.call(path+'/execution-status'));return 0
    if args.command=='artifacts':output({'project':rid,'artifacts':api.call(path)['artifacts'],'catalog':api.call(path+'/results')});return 0
    if args.command=='run':
        if args.timeout<=0 or not .2<=args.poll<=60:raise ValueError('timeout需为正数，poll范围0.2至60秒')
        if args.mode:api.call(path+'/mode',{'review_mode':args.mode},'PUT')
        # Begin at current cursor, not a replay of every historical token.
        current=api.call(path+'/execution-status');cursor=current['event_cursor']
        scope={}
        if args.case is not None:scope['case_ids']=args.case
        if args.all_cases:scope['case_ids']=[]
        if args.priority_case is not None:scope['priority_cases']=args.priority_case
        value=api.call(path+'/run',scope);output({'kind':'started',**value});prior=rid;rid=value['project_id'];path='projects/'+rid
        if rid!=prior:cursor=0
        if not args.wait:return 0
        deadline=time.monotonic()+args.timeout;previous=None
        while True:
            events=api.call(path+'/events/history?'+urllib.parse.urlencode({'after':cursor,'limit':200}))['events']
            for event in events:cursor=max(cursor,event['id']);output({'kind':'execution_event','project':rid,'event_cursor':cursor,'event':event})
            value=api.call(path+'/execution-status');signature=json.dumps(value,sort_keys=True)
            if signature!=previous:output({'kind':'status',**value});previous=signature
            if value['job']['status']!='running':
                output({'kind':'finished',**value,'web_url':api.server if hasattr(api,'server') else args.server});return 0 if value.get('execution_complete',value['complete']) else 2
            if time.monotonic()>=deadline:output({'kind':'detached','project':rid,'reason':'CLI等待超时；服务端运行继续，可在网页查看或再次status/events'});return 3
            time.sleep(args.poll)
    raise ValueError('unsupported command')

def entry():
    try:return main()
    except (ValueError,OSError) as e:output({'error':str(e)});return 2
