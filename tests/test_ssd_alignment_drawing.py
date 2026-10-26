import xml.etree.ElementTree as ET
from copy import deepcopy
from scene_completion.ssd_drawing import render_fused_ssd
from tests.test_workflow import memory_inputs

def test_render_only_confirmed_saved_refinements_with_visible_numbers(tmp_path):
    x=memory_inputs();rr=deepcopy(x['sr-ssd']['interactions'][0]);rr.update(id='rr1',layer='RR',sequence=1)
    sr=deepcopy(x['sr-ssd']['interactions'][0]);sr.update(id='sr1',layer='SR',sequence=1)
    other=deepcopy(rr);other.update(id='rr2',sequence=2)
    value={'interactions':[rr,sr,other],'rr_sr_links':[{'rr_id':'rr1','sr_ids':['sr1'],'status':'confirmed','basis':'Explicit expansion <&>'},{'rr_id':'rr2','sr_ids':['sr1'],'status':'pending','basis':'uncertain'}]}
    file=tmp_path/'ssd.svg';render_fused_ssd(value,file);root=ET.parse(file).getroot()
    groups=[g for g in root.iter() if g.get('data-rr-id')]
    assert len(groups)==1 and groups[0].get('data-rr-id')=='rr1' and groups[0].get('data-sr-ids')=='sr1'
    text=''.join(root.itertext());assert 'RR 1 → SR 1' in text and '未保存已确认的SR对应' in text
    assert 'Explicit expansion <&>' in text
    assert {n.get('data-message-id') for n in root.iter() if n.get('data-message-id')}=={'rr1','rr2','sr1'}

def test_unmapped_SR_shown_as_unassigned_not_fabricated(tmp_path):
    x=memory_inputs();value={'interactions':x['rr-ssd']['interactions']+x['sr-ssd']['interactions'],'rr_sr_links':[]}
    file=tmp_path/'ssd.svg';render_fused_ssd(value,file);root=ET.parse(file).getroot()
    assert not any(g.get('data-rr-id') for g in root.iter())
    assert '未保存已确认的RR归属' in ''.join(root.itertext())
