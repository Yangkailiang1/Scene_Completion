"""Start the local offline-capable review UI; model calls use configured intranet API."""
from pathlib import Path
import argparse,sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'.cac/tools'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8765);parser.add_argument('--data-dir');parser.add_argument('--env-file')
    args=parser.parse_args()
    import uvicorn
    from scene_completion.workbench import create_app
    uvicorn.run(create_app(args.data_dir,env_file=args.env_file),host=args.host,port=args.port)
if __name__=='__main__':main()
