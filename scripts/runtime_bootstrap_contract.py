"""Deterministic request inventory; absence does not imply mandatory dependency."""
import re


def integer(value,minimum=0,maximum=2**31-1):
    return type(value) is int and minimum<=value<=maximum


def classify(trace):
    if type(trace) is not list or len(trace)>8192:raise ValueError('trace scope')
    counts=dict(rows=len(trace),lookups=0,resolved=0,null_success=0,unsupported_request=0,
                invalid_request=0,other_request_error=0,actual_calls=0,failed_calls=[],
                mandatory_apis_established=False)
    for row in trace:
        if type(row) is not dict or type(row.get('symbol')) is not str or len(row['symbol'])>256:
            raise ValueError('trace row/symbol')
        if not re.fullmatch(r'(?:[A-Za-z_][A-Za-z_0-9]*|<null>|<ordinal>)?',row['symbol']):
            raise ValueError('trace symbol format')
        kind=row.get('kind')
        if kind=='lookup':
            if set(row)!={'kind','symbol','found'} or type(row['found']) is not bool:raise ValueError('lookup row')
            counts['lookups']+=1
        elif kind in ('resolver_v1','resolver_v2'):
            fields={'kind','symbol','version','flags','result','found'}|({'status'} if kind=='resolver_v2' else set())
            if (set(row)!=fields or not integer(row['version'],-2**31) or not integer(row['flags'],0,2**64-1)
                    or not integer(row['result']) or row['found'] is not None and type(row['found']) is not bool):
                raise ValueError('resolver row')
            status=row.get('status')
            if status is not None and not integer(status,0,2):raise ValueError('resolver query status')
            if row['result']==0:
                if type(row['found']) is not bool:raise ValueError('successful resolver without output slot')
                if kind=='resolver_v1' and not row['found']:raise ValueError('legacy success without pointer')
                if status is not None and (status==0)!=row['found']:raise ValueError('resolver pointer/status mismatch')
            category=('resolved' if row['found'] else 'null_success') if row['result']==0 else (
                'unsupported_request' if row['result']==801 else 'invalid_request' if row['result']==1 else 'other_request_error')
            counts[category]+=1
        elif kind=='call':
            field='value' if row['symbol']=='cuDriverGetVersion' else 'flags' if row['symbol']=='cuInit' else None
            if (field is None or set(row)!={'kind','symbol','result',field} or not integer(row['result'])):
                raise ValueError('observed call row')
            if field=='flags' and not integer(row[field],0,2**32-1):raise ValueError('unsigned init flags')
            if field=='value' and row[field] is not None and not integer(row[field],-2**31,2**31-1):
                raise ValueError('signed version output')
            counts['actual_calls']+=1
            if row['result']!=0:counts['failed_calls'].append(row['symbol'])
        else:raise ValueError('unknown trace kind')
    counts['failed_calls']=sorted(set(counts['failed_calls']))
    return counts


def version_only(value):
    try:
        return (type(value['code']) is int and value['code']==0
                and type(value['value']) is int and value['value']==12090
                and value['trace']==[] and value['restored'] is True
                and type(value['patches']) is int and value['patches']>=0)
    except (KeyError,TypeError):return False


def native_prefix(nominal,observed):
    try:
        summary=classify(observed['trace'])
        return (type(nominal['code']) is int and nominal['code']==35 and nominal['trace']==[]
                and type(nominal['patches']) is int and nominal['patches']==0 and nominal['restored'] is True
                and type(observed['code']) is int and observed['code']==35
                and type(nominal['value']) is int and type(observed['value']) is int
                and nominal['value']==observed['value'] and observed['restored'] is True
                and type(observed['patches']) is int and observed['patches']>0
                and summary['failed_calls']==['cuDriverGetVersion']
                and [row for row in observed['trace'] if row['kind']=='call']==[
                    dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0)])
    except (KeyError,TypeError,ValueError):return False
