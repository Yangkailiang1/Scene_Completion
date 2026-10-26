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

def output(value):print(json.dumps(value,ensure_ascii=False),flush=True)

def parser():
    p=argparse.ArgumentParser(description='让Code Agent操作同一网页工作台；输出JSON或JSONL，不另建隐藏运行目录。');p.add_argument('--server',default='http://127.0.0.1:8765');sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('projects');create=sub.add_parser('create');create.add_argument('--name',required=True)
    for role in ('rr','sr','test'):create.add_argument('--'+role,action='append',required=role!='test',default=[])
    create.add_argument('--mode',choices=('manual','auto'),default='manual');create.add_argument('--case',action='append',default=[])
    accounts=sub.add_parser('accounts')
    save=sub.add_parser('save-account');save.add_argument('--id');save.add_argument('--name',required=True);save.add_argument('--base-url',required=True);save.add_argument('--model',action='append',required=True);group=save.add_mutually_exclusive_group();group.add_argument('--api-key-env');group.add_argument('--prompt-key',action='store_true',help='终端隐藏输入API Key；密钥不进入命令历史')
    for cmd in ('status','artifacts','run','events','configure','guide','answer'):
        a=sub.add_parser(cmd);a.add_argument('--project',required=True)
        if cmd=='run':a.add_argument('--wait',action='store_true');a.add_argument('--mode',choices=('manual','auto'));a.add_argument('--timeout',type=float,default=3600);a.add_argument('--poll',type=float,default=2)
        if cmd=='events':a.add_argument('--after',type=int,default=0);a.add_argument('--node');a.add_argument('--limit',type=int,default=200)
        if cmd=='configure':a.add_argument('--account',required=True);a.add_argument('--model',required=True);a.add_argument('--concurrency',type=int,default=2)
        if cmd in ('guide','answer'):a.add_argument('--node',required=True);a.add_argument('--text',required=True)
        if cmd=='answer':a.add_argument('--question',required=True)
    return p

def main(argv=None,client=None):
    args=parser().parse_args(argv);api=client or API(args.server)
    if args.command=='projects':output(api.call('projects'));return 0
    if args.command=='accounts':output(api.call('model-accounts'));return 0
    if args.command=='save-account':
        accounts=api.call('model-accounts');body={'expected_revision':accounts['revision'],'name':args.name,'base_url':args.base_url,'models':args.model}
        if args.id:body['id']=args.id
        if args.api_key_env:body['api_key_env']=args.api_key_env
        if args.prompt_key:body['api_key']=getpass.getpass('API Key（隐藏输入）: ')
        output(api.call('model-accounts',body,'PUT'));return 0
    if args.command=='create':
        sources={}
        for role in ('rr','sr','test'):
            sources['test' if role=='test' else role.upper()]=[]
            for name in getattr(args,role):
                file=Path(name);row={'name':file.name}
                if file.suffix.lower()=='.xlsx' and role=='test':row['content_base64']=base64.b64encode(file.read_bytes()).decode()
                else:row['content']=file.read_text(encoding='utf-8-sig')
                sources['test' if role=='test' else role.upper()].append(row)
        output(api.call('projects',{'name':args.name,'sources':sources,'review_mode':args.mode,'case_ids':args.case}));return 0
    rid=args.project
    if len(rid)!=32 or any(c not in '0123456789abcdef' for c in rid):raise ValueError('项目ID必须是工作台返回的32位ID')
    path='projects/'+rid
    if args.command=='configure':output(api.call(path+'/config',{'model_account_id':args.account,'agent_model':args.model,'max_concurrency':args.concurrency},'PUT'));return 0
    if args.command=='guide':output(api.call(path+'/conversation',{'task_key':args.node,'text':args.text}));return 0
    if args.command=='answer':output(api.call(path+'/answer',{'task_key':args.node,'question_id':args.question,'text':args.text}));return 0
    if args.command=='events':
        query=urllib.parse.urlencode({'after':args.after,'limit':args.limit,**({'task_key':args.node} if args.node else {})});output(api.call(path+'/events/history?'+query));return 0
    if args.command=='status':output(api.call(path+'/execution-status'));return 0
    if args.command=='artifacts':output({'project':rid,'artifacts':api.call(path)['artifacts'],'catalog':api.call(path+'/results')});return 0
    if args.command=='run':
        if args.timeout<=0 or not .2<=args.poll<=60:raise ValueError('timeout需为正数，poll范围0.2至60秒')
        if args.mode:api.call(path+'/mode',{'review_mode':args.mode},'PUT')
        # Begin at current cursor, not a replay of every historical token.
        current=api.call(path+'/execution-status');cursor=current['event_cursor']
        value=api.call(path+'/run',{});output({'kind':'started',**value});prior=rid;rid=value['project_id'];path='projects/'+rid
        if rid!=prior:cursor=0
        if not args.wait:return 0
        deadline=time.monotonic()+args.timeout;previous=None
        while True:
            events=api.call(path+'/events/history?'+urllib.parse.urlencode({'after':cursor,'limit':200}))['events']
            for event in events:cursor=max(cursor,event['id']);output({'kind':'execution_event','project':rid,'event_cursor':cursor,'event':event})
            value=api.call(path+'/execution-status');signature=json.dumps(value,sort_keys=True)
            if signature!=previous:output({'kind':'status',**value});previous=signature
            if value['job']['status']!='running':
                output({'kind':'finished',**value,'web_url':api.server if hasattr(api,'server') else args.server});return 0 if value['complete'] else 2
            if time.monotonic()>=deadline:output({'kind':'detached','project':rid,'reason':'CLI等待超时；服务端运行继续，可在网页查看或再次status/events'});return 3
            time.sleep(args.poll)
    raise ValueError('unsupported command')

def entry():
    try:return main()
    except (ValueError,OSError) as e:output({'error':str(e)});return 2
