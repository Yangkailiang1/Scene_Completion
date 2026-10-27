"""Conservative request-wide context bound; never a provider token count."""
import json
DEFAULT_LIMIT=200000

def estimate(body):
    total=0
    for message in body.get('messages',[]):
        content=message.get('content')
        total += len(content.encode('utf8'))+len(json.dumps({k:v for k,v in message.items() if k!='content'},ensure_ascii=False).encode())+256 if isinstance(content,str) else len(json.dumps(message,ensure_ascii=False).encode())+256
    # Schema/tools and all other request metadata are part of the bound too.
    total += len(json.dumps({k:v for k,v in body.items() if k not in {'messages','max_tokens','max_completion_tokens'}},ensure_ascii=False).encode())
    return {'estimated_input_tokens_upper_bound':total,'output_reserve':body.get('max_tokens',body.get('max_completion_tokens')),'estimate_method':'UTF-8 bytes plus message framing; conservative upper bound, not provider tokenization'}

def check(body,config):
    limit=config.get('max_context_tokens',DEFAULT_LIMIT)
    if type(limit) is not int or limit<1:raise ValueError('max_context_tokens must be a positive integer')
    value=estimate(body);value['max_context_tokens']=limit
    if value['estimated_input_tokens_upper_bound']+value['output_reserve']>limit:
        error=RuntimeError('task context exceeds configured budget; split scoped task without truncating evidence')
        error.response_diagnostic={'failure_category':'context_budget_exceeded','configuration_required':True,'not_sent':True,**value}
        raise error
    return value
