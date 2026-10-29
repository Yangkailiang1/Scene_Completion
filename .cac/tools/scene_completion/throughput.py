"""Windowed provider throughput. Byte estimates are labelled, never token billing."""
from collections import deque
import time


class SlowStream(RuntimeError):
    def __init__(self,diagnostic):
        super().__init__('stream cancelled by configured low-throughput policy')
        self.response_diagnostic={'failure_category':'slow_stream','phase':'stream_read','client_cancelled':True,'usage_unknown':True,**diagnostic}


class Monitor:
    def __init__(self,policy,started=None,clock=None,model=None):
        self.model=model;self.policy=policy;self.clock=clock or time.perf_counter;self.started=started if started is not None else self.clock()
        self.samples=deque([(self.started,0)]);self.total=0;self.last_output=self.started;self.last_window=self.started;self.low=0;self.last_emit=self.started;self.channels={}
    def observe(self,byte_count,*,final=False,**channels):
        now=self.clock();p=self.policy() or {}
        if byte_count>self.total:self.last_output=now
        self.total=byte_count;self.samples.append((now,byte_count));self.channels.update(channels)
        window=p.get('window_seconds',30)
        while len(self.samples)>2 and self.samples[1][0]<=now-window:self.samples.popleft()
        age=now-self.started;span=max(.001,now-self.samples[0][0]);rate=max(0,byte_count-self.samples[0][1])/4/span
        row={**self.channels,'last_output_age_seconds':round(now-self.last_output,2),'requested_model':self.model,'elapsed_seconds':round(age,2),'window_seconds':round(span,2),'tokens_per_second_estimate':round(rate,3),'output_bytes':byte_count,'measurement':'UTF-8 bytes / 4 (estimate, includes reasoning; not billing)','threshold':p.get('min_tokens_per_second',2),'enabled':bool(p.get('enabled'))}
        from .execution_events import emit
        if final or now-self.last_emit>=5:
            emit('throughput_sample',**row);self.last_emit=now
        if final or not p.get('enabled') or age<p.get('grace_seconds',60):return row
        self.last_window=max(self.last_window,self.started+p.get('grace_seconds',60))
        if now-self.last_output>=p.get('no_output_seconds',120):raise SlowStream({**row,'reason':'no_generated_output','last_output_age_seconds':round(now-self.last_output,2)})
        if now-self.last_window>=window:
            self.last_window=now;self.low=self.low+1 if rate<p.get('min_tokens_per_second',2) else 0
            if self.low>=p.get('low_windows',2):raise SlowStream({**row,'reason':'sustained_low_throughput','low_windows':self.low})
        return row
    def timeout(self):
        self.observe(self.total)

    def read_wait(self):
        p=self.policy()
        if not p.get('enabled'):return None
        now=self.clock()
        return max(.01,p.get('grace_seconds',60)-(now-self.started),p.get('no_output_seconds',120)-(now-self.last_output))
