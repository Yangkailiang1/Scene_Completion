"""Reentrant process/thread serialization for versioned project configuration."""
from pathlib import Path
from contextlib import contextmanager
from functools import wraps
from threading import RLock,local
from .scheduler import run_lock
_lock=RLock();_local=local()
@contextmanager
def configuration_lock(project):
 key=str(Path(project).resolve())
 with _lock:
  held=getattr(_local,'held',set())
  if key in held:yield;return
  with run_lock(Path(project)/'.configuration'):
   _local.held=held|{key}
   try:yield
   finally:_local.held=held

def serialized(fn):
 @wraps(fn)
 def call(project,*args,**kwargs):
  with configuration_lock(project):return fn(project,*args,**kwargs)
 return call
