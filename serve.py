"""Start the local offline-capable review UI; model calls use configured intranet API."""
from pathlib import Path
import argparse,sys,json,os,secrets,time
sys.path.insert(0,str(Path(__file__).resolve().parent/'.cac/tools'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8765);parser.add_argument('--data-dir');parser.add_argument('--env-file');parser.add_argument('--control-file')
    args=parser.parse_args()
    import uvicorn
    from scene_completion.workbench import create_app
    app=create_app(args.data_dir,env_file=args.env_file)
    server=uvicorn.Server(uvicorn.Config(app,host=args.host,port=args.port))
    control=Path(args.control_file).resolve() if args.control_file else None
    token=secrets.token_hex(32)
    if control:
        from scene_completion.storage import write_json
        control.parent.mkdir(parents=True,exist_ok=True)
        write_json(control,{'pid':os.getpid(),'port':args.port,'token':token,'started_at':time.time()})
        from fastapi import Request,HTTPException
        globals()["Request"]=Request
        @app.post('/api/runtime/control')
        def runtime_control(request:Request,body:dict):
            if not secrets.compare_digest(request.headers.get('authorization',''),'Bearer '+token):raise HTTPException(403,'Control token mismatch')
            if body.get('action')=='stop':
                from scene_completion.worker_runtime import stop_workers
                stop_workers(app.state.workbench);server.should_exit=True
            elif body.get('action')!='status':raise HTTPException(400,'Unknown control action')
            return {'pid':os.getpid(),'port':args.port,'status':'stopping' if server.should_exit else 'running'}
    try:server.run()
    finally:
        if control and control.exists() and json.loads(control.read_text()).get('token')==token:control.unlink()

if __name__=='__main__':main()
