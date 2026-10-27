"""Content identities and atomic JSON IO, including portable Windows long paths."""
from __future__ import annotations
import hashlib,json,os,tempfile,ntpath
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode('utf8')).hexdigest()


def windows_extended_path(path):
    text=str(path)
    if text.startswith('\\\\?\\'):return text
    absolute=ntpath.abspath(text)
    return '\\\\?\\UNC\\'+absolute[2:] if absolute.startswith('\\\\') else '\\\\?\\'+absolute


def io_path(path):
    return Path(windows_extended_path(path)) if os.name=='nt' else Path(path)


def write_json(path: str | Path, value) -> None:
    target=io_path(path);temporary=None
    try:
        target.parent.mkdir(parents=True,exist_ok=True)
        # Avoid appending a second long identity to an already long filename.
        fd,name=tempfile.mkstemp(prefix='.sc-',suffix='.tmp',dir=target.parent)
        temporary=Path(name)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2)
        os.replace(temporary,target)
    except OSError as error:
        error.response_diagnostic={'failure_category':'artifact_io_error','operation':'atomic_json_write','path':str(path),'errno':error.errno,'path_characters':len(str(path)), 'windows_long_path_support':os.name=='nt'}
        raise
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass  # Preserve the original write/replace diagnostic.


def read_json(path: str | Path):
    return json.loads(io_path(path).read_text(encoding='utf-8'))
