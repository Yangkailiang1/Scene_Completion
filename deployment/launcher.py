"""Portable launcher. Uses only the Python runtime shipped beside this file."""
from pathlib import Path
import argparse,socket,subprocess,sys,time,urllib.request,webbrowser


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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('port must be between 1 and 65535')
    return run(Path(__file__).resolve().parent,args.port,not args.no_browser)

if __name__=='__main__':raise SystemExit(main())
