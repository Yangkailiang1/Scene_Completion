import os
import subprocess
import sys
import time

import pytest

from scene_completion.delivery_job import status
from scene_completion.semantic_backend import write_json


def test_status_distinguishes_missing_process_from_accepted_delivery(tmp_path):
    assert status(tmp_path)['status'] == 'not_started'
    write_json(tmp_path / 'delivery_job.json', {'status': 'complete', 'ready_to_deliver': True})
    assert status(tmp_path)['ready_to_deliver']


@pytest.mark.skipif(os.name == 'nt', reason='POSIX host cleanup uses double-fork reparenting')
def test_detached_executor_finishes_after_controller_process_exits(tmp_path):
    from pathlib import Path
    done = tmp_path / 'done'
    code = ('from scene_completion.delivery_job import launch_detached; import sys; '
        'launch_detached([sys.executable,"-c",'
        + repr('import time;from pathlib import Path;time.sleep(.2);Path(' + repr(str(done)) + ').write_text("finished")')
        + '],cwd=' + repr(str(tmp_path)) + ',log=' + repr(str(tmp_path / 'job.log')) + ')')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / '.cac/tools')}
    subprocess.run([sys.executable, '-c', code], env=env, check=True, timeout=5)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not done.exists():
        time.sleep(.05)
    assert done.read_text() == 'finished'
