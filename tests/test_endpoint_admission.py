from concurrent.futures import ThreadPoolExecutor
import threading,time,multiprocessing
from scene_completion.endpoint_admission import endpoint_slot


def worker(directory,queue):
    with endpoint_slot('http://model/v1','credential',limit=2,directory=directory,timeout=10):
        queue.put(('enter',time.time()));time.sleep(.15);queue.put(('leave',time.time()))


def test_same_account_limit_is_shared_across_processes(tmp_path):
    ctx=multiprocessing.get_context('spawn');q=ctx.Queue();ps=[ctx.Process(target=worker,args=(str(tmp_path),q)) for _ in range(4)]
    for p in ps:p.start()
    events=[q.get(timeout=20) for _ in range(8)]
    for p in ps:p.join(10);assert p.exitcode==0
    active=peak=0
    for kind,_ in sorted(events,key=lambda e:e[1]):
        active+=1 if kind=='enter' else -1;peak=max(peak,active)
    assert active==0 and peak<=2


def test_slots_release_after_exception_and_credentials_do_not_share_slots(tmp_path):
    import pytest
    with pytest.raises(RuntimeError):
        with endpoint_slot('http://m','a',limit=1,directory=tmp_path):raise RuntimeError('task failed')
    with endpoint_slot('http://m','a',limit=1,directory=tmp_path,timeout=.1):
        with endpoint_slot('http://m','b',limit=1,directory=tmp_path,timeout=.1):pass
