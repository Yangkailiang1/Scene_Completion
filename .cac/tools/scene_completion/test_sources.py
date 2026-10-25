"""Typed test records shared by Markdown, XLSX, preview and scoring.

XLSX is data only: formulas, external links and macros are never evaluated.
Original workbook coordinates are retained in preview and evidence names.
"""
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET
import base64,re,posixpath
from .storage import fingerprint

VERSION='exception-test-sources-v1'
HEADERS=['测试ID','测试名称','类型','前置条件','触发条件','关联需求','测试目标','预期结果','需求依据','测试数据','测试步骤','关注点','来源方式','可执行性/待确认事项']
ALIASES={'测试ID':['测试ID','用例编号','测试编号','编号'],'测试名称':['测试名称','场景名称','测试场景'],
 '类型':['类型','场景类型','测试类型'],'前置条件':['前置条件'],'触发条件':['触发条件','测试动作','操作与输入','测试输入'],
 '关联需求':['关联需求','用例ID/名称','用例ID／名称','用例ID','交互/接口','交互／接口'],
 '测试目标':['测试目标'],'预期结果':['预期结果','预期输出'],'需求依据':['需求依据','来源依据','来源'],
 '测试数据':['测试数据'],'测试步骤':['测试步骤'],'关注点':['关注点'],'来源方式':['来源方式'],
 '可执行性/待确认事项':['可执行性/待确认事项','可执行性／待确认事项']}
ALIASES['需求依据'].append('来源定位')
KINDS={'异常':'exception','exception':'exception','正常':'normal','normal':'normal','可选':'optional','optional':'optional','待确认':'pending','pending':'pending'}

def cells(text):
    return [x.strip().replace(r'\|','|').replace('<br>','\n') for x in re.split(r'(?<!\\)\|',text.strip().strip('|'))]

def records(documents):
    out=[]
    for d in documents:
        header=None
        for row in d['lines']:
            if not row['text'].lstrip().startswith('|'):continue
            values=cells(row['text'])
            if any(v in ALIASES['测试ID'] for v in values):header=values;continue
            idcol=next((n for n,h in enumerate(header or HEADERS) if h in ALIASES['测试ID']),0)
            if len(values)<=idcol or not re.fullmatch(r'(?:TEST|SUP)[-_][A-Za-z0-9_-]+',values[idcol]):continue
            # A scoped historical table may omit its header. Its established
            # 9-column layout is the sole legacy fallback, not a text search.
            names=header or HEADERS
            item={k:next((values[j] for j,h in enumerate(names) if h in aliases and j<len(values)),'') for k,aliases in ALIASES.items()}
            item['关联需求']='；'.join(values[j] for j,h in enumerate(names) if h in ALIASES['关联需求'] and j<len(values) and values[j])
            item.update(id=item['测试ID'],scenario_type=KINDS.get(item['类型'].casefold(),'pending'),source_id=d['source_id'],name=d['name'],row=row['number'],
              source_refs=[{'source_id':d['source_id'],'line_start':row['number'],'line_end':row['number'],'quote':row['text']}])
            if '.xlsx#' in d['name']:
                filename,sheet=d['name'].split('#',1)
                def col(n):
                    text=''
                    while n:n,r=divmod(n-1,26);text=chr(65+r)+text
                    return text
                item['source_location']={'file':filename,'sheet':sheet,'row':row['number'],'cells':{h:col(n)+str(row['number']) for n,h in enumerate(names,1)}}
            out.append(item)
    return out

def exception_documents(documents):
    allowed={(r['source_id'],r['row']) for r in records(documents) if r['scenario_type']=='exception'}
    return [{**d,'lines':[r for r in d['lines'] if (d['source_id'],r['number']) in allowed or any(h in cells(r['text']) for h in ALIASES['测试ID'])]} for d in documents if any((d['source_id'],r['number']) in allowed for r in d['lines'])]

def preview(documents):
    rs=records(documents);seen=set();issues=[]
    known={(r['source_id'],r['row']) for r in rs}
    for d in documents:
        header=None
        for row in d['lines']:
            if not row['text'].lstrip().startswith('|'):continue
            values=cells(row['text'])
            if any(v in ALIASES['测试ID'] for v in values):header=values;continue
            if not header or not any(values) or all(re.fullmatch(r'[: -]*',v) for v in values):continue
            if (d['source_id'],row['number']) not in known:
                issues.append({'id':'','row':row['number'],'source':d['name'],'reason':'测试ID缺少或格式无效，请使用TEST-或SUP-开头的唯一编号'})
    for r in rs:
        if r['id'] in seen:issues.append({'id':r['id'],'row':r['row'],'source':r['name'],'reason':'重复测试ID'})
        seen.add(r['id'])
        missing=[k for k in ('测试ID','测试名称','前置条件','触发条件','关联需求','预期结果') if not r[k]]
        if missing:issues.append({'id':r['id'],'row':r['row'],'source':r['name'],'reason':'缺少：'+ '、'.join(missing)})
        if r['scenario_type']=='pending':issues.append({'id':r['id'],'row':r['row'],'source':r['name'],'reason':'场景类型缺失或未知，不参与计分'})
    return {'version':VERSION,'records':rs,'counts':{k:sum(r['scenario_type']==k for r in rs) for k in ('exception','normal','optional','pending')},'issues':issues,'valid':not any('重复' in x['reason'] or '缺少' in x['reason'] for x in issues)}

def markdown_row(values):
    return '| '+' | '.join(str(v or '').replace('|',r'\|').replace('\n','<br>') for v in values)+' |'

def xlsx_documents(data,name,identity):
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    relns='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    try:
        with ZipFile(BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist())>40_000_000:raise ValueError('Excel解压后超过40MB')
            if any('externalLinks/' in n or n.endswith('vbaProject.bin') for n in z.namelist()):raise ValueError('不接受宏或外部链接工作簿')
            shared=[]
            if 'xl/sharedStrings.xml' in z.namelist():
                shared=[''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)]
            rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
            docs=[]
            for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet',ns):
                label=sheet.attrib['name'];target=rels[sheet.attrib[relns]]
                path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
                rows=[];header=None
                for row in ET.fromstring(z.read(path)).findall('m:sheetData/m:row',ns):
                    vals={}
                    for cell in row.findall('m:c',ns):
                        if cell.find('m:f',ns) is not None:raise ValueError('测试表不接受公式单元格：'+label+'!'+cell.attrib.get('r',''))
                        address=cell.attrib.get('r','A1');col=0
                        for char in re.match(r'[A-Z]+',address)[0]:col=col*26+ord(char)-64
                        typ=cell.attrib.get('t');v=cell.find('m:v',ns)
                        text=''.join(cell.find('m:is',ns).itertext()) if typ=='inlineStr' and cell.find('m:is',ns) is not None else (v.text or '') if v is not None else ''
                        vals[col-1]=shared[int(text)] if typ=='s' and text else text
                    values=[vals.get(i,'') for i in range(max(vals,default=-1)+1)]
                    if any(v in ALIASES['测试ID'] for v in values):header=values
                    if header and values:rows.append({'number':int(row.attrib['r']),'text':markdown_row(values)})
                if rows:docs.append({'source_id':fingerprint(identity+'#'+label)[:20],'name':name+'#'+label,'channel':'test','lines':rows})
            return docs
    except (BadZipFile,ET.ParseError,KeyError,IndexError) as exc:raise ValueError('无效XLSX测试文件') from exc

def decode_source(d,role):
    suffix=Path(d.get('name','')).suffix.lower()
    if suffix=='.xlsx' and role=='test':
        try:data=base64.b64decode(d.get('content_base64',''),validate=True)
        except (ValueError,TypeError) as exc:raise ValueError('Excel需使用base64文件上传') from exc
        if not data or len(data)>5_000_000:raise ValueError('Excel为空或超过5MB')
        xlsx_documents(data,Path(d['name']).name,'preview')
        return data,suffix
    if suffix not in {'.md','.markdown'}:raise ValueError('RR/SR仅支持Markdown；测试支持Markdown或XLSX')
    content=d.get('content','')
    if not isinstance(content,str) or len(content.encode())>5_000_000:raise ValueError('文档无效或超过5MB')
    return content.encode(),'.md'
