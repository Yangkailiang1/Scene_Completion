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

def plain_header(value):return value.strip().strip('`*_').strip()

def is_test_header(values):
    values=[plain_header(v) for v in values]
    return any(v in ALIASES['测试ID'] for v in values) and any(v in ALIASES[k] for k in ('类型','触发条件','预期结果') for v in values)

def test_ids(text):
    return set(re.findall(r'\b(?:TEST|SUP)[-_][A-Za-z0-9_-]+|SC@[A-Za-z0-9_.:-]+',text))

def table_rows(document):
    header=None;fence=None
    for row in document['lines']:
        text=row['text'].lstrip('\ufeff').strip()
        marker=re.match(r'^(`{3,}|~{3,})',text)
        if marker:
            if fence is None:fence=marker[1][0]
            elif marker[1][0]==fence:fence=None
            header=None;continue
        if fence:continue
        if not text.startswith('|'):header=None;continue
        values=cells(text)
        if is_test_header(values):header=[plain_header(v) for v in values];continue
        if not any(values) or all(re.fullmatch(r'[: -]*',v) for v in values):continue
        yield row,values,header

def narrative_records(document):
    """Only explicitly typed recovered branches; no semantic reclassification."""
    result=[];case_id=case_name='';context=[];pre=[];collect=False;fence=None
    for row in document['lines']:
        text=row['text'].lstrip('\ufeff').strip()
        marker=re.match(r'^(`{3,}|~{3,})',text)
        if marker:
            if fence is None:fence=marker[1][0]
            elif marker[1][0]==fence:fence=None
            continue
        if fence:continue
        heading=re.match(r'^#{2,6}\s+([A-Za-z0-9][\w.-]*)\s*[:：]\s*(.+)',text)
        if heading:
            case_id,case_name=heading.groups();context=[row['number']];pre=[];collect=False
        if re.match(r'^\d+[.、]\s*前置条件\s*[:：]',text):
            collect=True;pre=[text.split('：',1)[-1] if '：' in text else text.split(':',1)[-1]];context.append(row['number']);continue
        if collect:
            if re.match(r'^\d+[.、]\s*|^[-*]\s+EXT\s*[:：]',text) or text.startswith('#'):collect=False
            else:
                if text:pre.append(text);context.append(row['number'])
        branch=re.match(r'^[-*]\s+EXT\s*[:：]\s*([A-Za-z_]+)\s*[:：]\s*(.*?)〔(SC@[A-Za-z0-9_.:-]+)〕\s*(?:→|->)\s*(.*)$',text)
        success=re.match(r'^\d+[.、]\s*主成功路径\s*[:：].*?〔(SC@[A-Za-z0-9_.:-]+)〕',text)
        if not branch and not success:continue
        if branch:kind,title,sid,expected=branch.groups()
        else:kind,title,sid,expected='normal','主成功路径',success[1],''
        declared={'exception':'exception','alternative_success':'normal','normal':'normal','optional':'optional','undetermined':'pending','pending':'pending'}.get(kind,'pending')
        item={k:'' for k in HEADERS};item.update({'测试ID':sid,'测试名称':title,'类型':{'exception':'异常','normal':'正常','optional':'可选','pending':'待确认'}[declared], '前置条件':'\n'.join(x for x in pre if x),'触发条件':title,'关联需求':case_id+('：'+case_name if case_name else ''),'预期结果':expected,'来源方式':'上传文档明示的恢复场景'})
        item.update(id=sid,case_name=case_name,scenario_type=declared,source_id=document['source_id'],name=document['name'],row=row['number'],source_format='recovered_usecase',declared_type=kind,context_rows=list(context),source_refs=[{'source_id':document['source_id'],'line_start':row['number'],'line_end':row['number'],'quote':row['text']}])
        # The main success path remains visible but never enters exception GT.
        if success:item['预期结果']='主成功路径（原文后续步骤）'
        result.append(item)
    # Case alignment gets the test's own goal/actors/success context, never a
    # neighbouring case or exception branch. Later partitions retain exact refs.
    sections={};owner=None;normal=True;fence=None
    for row in document['lines']:
        text=row['text'].strip()
        marker=re.match(r'^(`{3,}|~{3,})',text)
        if marker:
            if fence is None:fence=marker[1][0]
            elif marker[1][0]==fence:fence=None
            continue
        if fence:continue
        heading=re.match(r'^#{2,6}\s+([A-Za-z0-9][\w.-]*)\s*[:：]\s*(.+)',text)
        if heading:owner=heading[1];normal=True;sections.setdefault(owner,[])
        if re.match(r'^\d+[.、]\s*扩展路径|^[-*]\s+EXT\s*[:：]',text):normal=False
        if owner and normal and text:sections[owner].append(row['number'])
    for item in result:
        owner=item['关联需求'].split('：',1)[0]
        item['context_rows']=sections.get(owner,item['context_rows'])
    return result

def records(documents):
    out=[]
    for d in documents:
        for row,values,header in table_rows(d):
            idcol=next((n for n,h in enumerate(header or HEADERS) if h in ALIASES['测试ID']),0)
            if len(values)<=idcol:continue
            identifier=plain_header(values[idcol])
            if not identifier or len(identifier)>120 or (not header and not re.fullmatch(r'(?:TEST|SUP)[-_][A-Za-z0-9_-]+',identifier)):continue
            values[idcol]=identifier
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
        out.extend(narrative_records(d))
    return out

def exception_documents(documents):
    typed=records(documents);selected=[r for r in typed if r['scenario_type']=='exception']
    excluded={(r['source_id'],r['row']) for r in typed if r['scenario_type']!='exception'}
    allowed={(r['source_id'],n) for r in selected for n in [r['row'],*r.get('context_rows',[])]}
    return [{**d,'lines':[r for r in d['lines'] if ((d['source_id'],r['number']) in allowed and (d['source_id'],r['number']) not in excluded) or is_test_header(cells(r['text']))]} for d in documents if any((d['source_id'],r['number']) in allowed for r in d['lines'])]

def records_for_inputs(inputs):
    if 'test-inventory' in inputs:
        from .test_alignment import as_records
        return as_records(inputs['test-inventory'],inputs.get('test-documents',[]))
    return records(inputs.get('test-documents',[]))

def referenced_record_ids(refs,typed_records):
    return {r['id'] for r in typed_records if any(a['source_id']==b['source_id'] and a['line_start']<=b['line_end'] and b['line_start']<=a['line_end'] for a in refs for b in r['source_refs'])}

def preview(documents):
    rs=records(documents);seen=set();issues=[]
    known={(r['source_id'],r['row']) for r in rs}
    for d in documents:
        for row,values,header in table_rows(d):
            if not header:continue
            if (d['source_id'],row['number']) not in known:
                issues.append({'id':'','row':row['number'],'source':d['name'],'reason':'测试ID缺少或格式无效，请提供非空且不超过120字符的唯一编号'})
    for r in rs:
        if r['id'] in seen:issues.append({'id':r['id'],'row':r['row'],'source':r['name'],'reason':'重复测试ID'})
        seen.add(r['id'])
        missing=[k for k in ('测试ID','测试名称','前置条件','触发条件','关联需求','预期结果') if not r[k]]
        if missing:issues.append({'id':r['id'],'row':r['row'],'source':r['name'],'reason':'缺少：'+ '、'.join(missing)})
        if r['scenario_type']=='pending':issues.append({'id':r['id'],'row':r['row'],'source':r['name'],'reason':'原文标为待确认，不参与计分' if r.get('declared_type') in {'undetermined','pending'} else '场景类型缺失或未知，不参与计分'})
    deferred=[d['name'] for d in documents if not any(r['source_id']==d['source_id'] for r in rs) and any(r['text'].strip() for r in d['lines'])]
    return {'version':VERSION,'records':rs,'counts':{k:sum(r['scenario_type']==k for r in rs) for k in ('exception','normal','optional','pending')},'issues':issues,'semantic_index_required':deferred,'valid':not any('重复' in x['reason'] or '缺少' in x['reason'] for x in issues)}

class ImportValidationError(ValueError):
    def __init__(self,checked):
        self.import_preview=checked
        details=[f"{x['source']} 第{x['row']}行 {x['id']}：{x['reason']}" for x in checked['issues']]
        super().__init__('测试导入校验未通过：'+'；'.join(details[:10]))

def preview_sources(sources):
    documents=[]
    for d in sources:
        data,suffix=decode_source(d,'test');identity=fingerprint([d['name'],data.hex()])
        documents.extend(xlsx_documents(data,d['name'],identity) if suffix=='.xlsx' else [{'source_id':identity[:20],'name':d['name'],'channel':'test','lines':[{'number':n,'text':text} for n,text in enumerate(data.decode('utf-8-sig').splitlines(),1)]}])
    return preview(documents)

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
