"""Portable launcher. Uses only the Python runtime shipped beside this file."""
from pathlib import Path
import argparse,socket,subprocess,sys,time,urllib.request,webbrowser,json,os


def run(bundle,port=8765,open_browser=True):
    bundle=Path(bundle).resolve();server=bundle/'app/serve.py'
    if not server.is_file():
        print('请先完整解压离线包，再运行 start.cmd。');return 1
    url=f'http://127.0.0.1:{port}'
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',port))==0:
            print(f'端口 {port} 已占用。请关闭原工作台，或运行 start.cmd --port 8766。');return 1
    command=[sys.executable,'-X','utf8',str(server),'--port',str(port),'--data-dir',str(bundle/'data'),'--env-file',str(bundle/'.env')]
    process=subprocess.Popen(command,cwd=bundle)
    try:
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            code=process.poll()
            if code is not None:
                print(f'工作台启动失败（退出码 {code}），请保留上面的错误信息。');return code or 1
            try:
                with urllib.request.urlopen(url+'/api/projects',timeout=1) as response:
                    ready=response.status==200
            except (OSError,ValueError):ready=False
            if ready:
                print('工作台已就绪：'+url,flush=True)
                if (bundle/'data/.review-mode.json').exists():
                    print('当前为业务审核模式，无需配置模型；完成回答和推荐审核后，请在审核交接页导出反馈。',flush=True)
                else:print('首次使用请在页面中配置客户内网模型地址、模型名称和密钥。',flush=True)
                if open_browser:
                    try:webbrowser.open(url)
                    except Exception:print('自动打开浏览器失败，请手动访问上面的地址。')
                return process.wait()
            time.sleep(.2)
        print('启动超过45秒，请检查上方日志或运行 check.cmd。');return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()


def control(bundle,action):
    path=Path(bundle)/'data/runtime-control.json'
    try:
        record=json.loads(path.read_text(encoding='utf8'))
        url=f"http://127.0.0.1:{int(record['port'])}/api/runtime/control"
        request=urllib.request.Request(url,data=json.dumps({'action':action}).encode(),headers={'Authorization':'Bearer '+record['token'],'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=5) as response:result=json.load(response)
        if result['pid']!=record['pid']:raise ValueError('服务身份不一致')
        print(json.dumps(result,ensure_ascii=False));return 0
    except (OSError,ValueError,KeyError):
        print('后台服务当前不可连接；未终止任何未知进程。请查看data/server.log。');return 1


def background(bundle,port=8765,open_browser=True):
    bundle=Path(bundle).resolve();server=bundle/'app/serve.py'
    if not server.is_file():print('请完整解压离线包。');return 1
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',port))==0:
            if control(bundle,'status')==0:
                if open_browser:webbrowser.open(f'http://127.0.0.1:{port}')
                return 0
            print('端口已由其他程序占用，请使用--port指定空闲端口。');return 1
    data=bundle/'data';data.mkdir(exist_ok=True)
    command=[sys.executable,'-X','utf8',str(server),'--port',str(port),'--data-dir',str(data),'--env-file',str(bundle/'.env'),'--control-file',str(data/'runtime-control.json')]
    kwargs={'cwd':bundle,'stdin':subprocess.DEVNULL}
    if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP
    else:kwargs['start_new_session']=True
    with (data/'server.log').open('ab') as log:process=subprocess.Popen(command,stdout=log,stderr=log,**kwargs)
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        if process.poll() is not None:print('启动失败，请查看data/server.log。');return 1
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/projects',timeout=1) as response:ready=response.status==200
            if ready:
                print(f'后台服务已就绪：http://127.0.0.1:{port}；关闭本窗口或浏览器不停止任务。')
                if open_browser:webbrowser.open(f'http://127.0.0.1:{port}')
                return 0
        except OSError:pass
        time.sleep(.2)
    print('服务仍在启动，请运行status.cmd查看；日志位于data/server.log。');return 1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--no-browser',action='store_true');parser.add_argument('--background',action='store_true');parser.add_argument('--status',action='store_true');parser.add_argument('--stop',action='store_true');args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('port must be between 1 and 65535')
    bundle=Path(__file__).resolve().parent
    if args.status or args.stop:return control(bundle,'stop' if args.stop else 'status')
    return (background if args.background else run)(bundle,args.port,not args.no_browser)

if __name__=='__main__':raise SystemExit(main())
