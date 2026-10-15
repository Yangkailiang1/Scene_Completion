"""Optional sidecar telemetry; never part of semantic inputs or proof identities."""
from contextlib import contextmanager
from contextvars import ContextVar
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json
import threading
import time
import uuid

_context = ContextVar('scene_performance_context', default={})
_active_profiler = ContextVar('scene_active_profiler', default=None)


class Profiler:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.session = uuid.uuid4().hex
        self.started = time.perf_counter()
        self.lock = threading.RLock()
        self.path = self.root/'performance_events.jsonl'
        self.emit('session', 'start')

    def emit(self, kind, status='complete', **values):
        row = {**_context.get(), 'session': self.session, 'kind': kind, 'status': status,
            'at': datetime.now(timezone.utc).isoformat(), 'offset_seconds': time.perf_counter()-self.started, **values}
        with self.lock, self.path.open('a', encoding='utf8') as file:
            file.write(json.dumps(row, ensure_ascii=False)+'\n')

    @contextmanager
    def span(self, kind, **values):
        start = time.perf_counter()
        token = _context.set({**_context.get(), **values})
        active_token = _active_profiler.set(self)
        details = {}
        try:
            yield details
        except BaseException as exc:
            diagnostic=getattr(exc,'response_diagnostic',{}) or {}
            details.update(error_type=type(exc).__name__, failure_category=
                diagnostic.get('failure_category'))
            if kind=='request':details.update(transport_attempts=diagnostic.get('transport_attempts'),usage=diagnostic.get('usage'))
            self.emit(kind, 'failed', start_seconds=start-self.started, duration_seconds=time.perf_counter()-start, **details)
            raise
        else:
            self.emit(kind, start_seconds=start-self.started, duration_seconds=time.perf_counter()-start, **details)
        finally:
            _context.reset(token)
            _active_profiler.reset(active_token)

    def finish(self, status='complete'):
        self.emit('session', status, duration_seconds=time.perf_counter()-self.started)
        self.report()

    def report(self):
        from .semantic_backend import write_json
        rows = [json.loads(line) for line in self.path.read_text(encoding='utf8').splitlines() if line]
        sessions = {}
        task_intervals=defaultdict(list)
        graph=defaultdict(dict)
        open_requests=defaultdict(int)
        for row in rows:
            session = sessions.setdefault(row['session'], {'session': row['session'], 'stages': {}, 'request_count': 0,
                'request_seconds': 0., 'task_seconds': 0., 'usage': {}, 'unknown_usage_requests': 0,
                'reported_http_attempts':0, 'requests_with_unknown_attempts':0,
                'wall_seconds':None, 'status':'incomplete_or_running', 'last_observed_seconds':0.})
            session['last_observed_seconds']=max(session['last_observed_seconds'],row.get('offset_seconds',0.))
            if row['kind']=='session' and row['status']!='start':
                session.update(wall_seconds=row['duration_seconds'], status=row['status'],
                    wall_measurement=row.get('measurement','monotonic'))
            stage = session['stages'].setdefault(row.get('stage', '@setup'), {'task_seconds':0., 'request_seconds':0.,
                'queue_seconds':0., 'validation_seconds':0., 'requests':0, 'repairs':0, 'cache_hits':0, 'failures':0})
            request_key=(row['session'],row.get('stage','@setup'),row.get('task_key'),row.get('batch_id'))
            if row['kind']=='transport_attempt_start' and row.get('attempt')==1:
                open_requests[request_key]+=1
            if row['kind']=='task':
                duration=row['duration_seconds']; stage['task_seconds']+=duration;session['task_seconds']+=duration
                stage['repairs']+=row.get('phase')=='repair'
                stage['queue_seconds']+=row.get('queue_seconds',0.)
                task_intervals[row['session']].append((row['start_seconds'],row['start_seconds']+duration))
                key=row.get('task_key',row.get('case','')+':'+row.get('stage',''))
                node=graph[row['session']].setdefault(key,{'duration':0.,'deps':row.get('dependencies',[])})
                node['duration']+=duration
            if row['kind']=='validation':stage['validation_seconds']+=row['duration_seconds']
            if row['kind']=='cache':stage['cache_hits']+=1
            if row['kind']=='request':
                open_requests[request_key]=max(0,open_requests[request_key]-1)
                stage['requests']+=1;session['request_count']+=1
                duration=row['duration_seconds'];stage['request_seconds']+=duration;session['request_seconds']+=duration
                stage['request_bytes']=stage.get('request_bytes',0)+row.get('request_bytes',0)
                stage['response_bytes']=stage.get('response_bytes',0)+row.get('response_bytes',0)
                if type(row.get('transport_attempts')) is int:
                    stage['transport_retries']=stage.get('transport_retries',0)+max(0,row['transport_attempts']-1)
                    session['reported_http_attempts']+=row['transport_attempts']
                else:session['requests_with_unknown_attempts']+=1
                stage['failures']+=row['status']=='failed'
                usage=row.get('usage')
                if not usage:session['unknown_usage_requests']+=1
                else:
                    for key,value in usage.items():
                        if type(value) in (int,float):session['usage'][key]=session['usage'].get(key,0)+value
        for sid,session in sessions.items():
            session['unfinished_request_count']=sum(n for key,n in open_requests.items() if key[0]==sid)
            intervals=sorted(task_intervals[sid]);end=-1.;busy=0.
            for start,stop in intervals:
                busy+=max(0.,stop-max(start,end));end=max(end,stop)
            session['task_busy_seconds']=busy
            session['task_overlap_seconds']=max(0.,session['task_seconds']-busy)
            nodes=graph[sid];memo={}
            def longest(key):
                if key not in nodes:return (0.,[])
                if key not in memo:
                    best=max((longest(dep) for dep in nodes[key]['deps']),default=(0.,[]),key=lambda v:v[0])
                    memo[key]=(best[0]+nodes[key]['duration'],best[1]+[key])
                return memo[key]
            value,path=max((longest(key) for key in nodes),default=(0.,[]),key=lambda v:v[0])
            session['dependency_path']={'task_seconds':value,'tasks':path,
                'note':'Observed task-duration dependency path; excludes queue, final validation and setup overhead.'}
        payload={'schema':'scene-performance-v1','sessions':list(sessions.values()),
            'note':'Task/request/validation spans overlap and must not be added together. Usage is provider-reported; missing values remain unknown.',
            'events_file':self.path.name}
        write_json(self.root/'performance.json',payload)
        lines=['# 阶段性能记录','',payload['note'],'']
        for session in payload['sessions']:
            wall = (f"{session['wall_seconds']:.2f} 秒" if session['wall_seconds'] is not None
                else f"未结束（最后记录至 {session['last_observed_seconds']:.2f} 秒）")
            lines += [f"## 运行 {session['session']}", '',
                f"墙钟时间：{wall}；逻辑请求数：{session['request_count']}；已记录HTTP尝试：{session['reported_http_attempts']}；未返回用量的请求：{session['unknown_usage_requests']}",
                f"墙钟计时依据：{session.get('wall_measurement','未结束')}；尚未取得完整结束记录的请求：{session['unfinished_request_count']}（耗时及用量未知，不能按零处理）",
                '', '| 阶段 | 任务秒 | 请求秒 | 排队秒 | 校验秒 | 请求数 | 修复尝试 | 缓存命中 |',
                '|---|---:|---:|---:|---:|---:|---:|---:|']
            for name,stage in sorted(session['stages'].items(),key=lambda p:-p[1]['task_seconds']):
                lines.append(f"| {name} | {stage['task_seconds']:.2f} | {stage['request_seconds']:.2f} | {stage['queue_seconds']:.2f} | {stage['validation_seconds']:.2f} | {stage['requests']} | {stage['repairs']} | {stage['cache_hits']} |")
            lines += ['', '接口用量：'+json.dumps(session['usage'],ensure_ascii=False),'']
        (self.root/'performance.md').write_text('\n'.join(lines),encoding='utf8')


@contextmanager
def span(profiler, kind, **values):
    if profiler:
        with profiler.span(kind, **values) as details:
            yield details
    else:
        yield {}


def size(value):
    return len(json.dumps(value,ensure_ascii=False,default=str).encode('utf8'))
