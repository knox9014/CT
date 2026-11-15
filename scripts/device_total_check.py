"""Bounded original-header device-total native results; no app claim."""
import re


def validate(value,*,forwarded):
    if (type(forwarded) is not bool or type(value) is not dict
            or set(value)!={'status','checks','total_bytes','device_name','tls_preserved','canaries','unloaded','forwarded'}
            or value['status']!='pass' or type(value['checks']) is not int or value['checks']!=(42 if forwarded else 39)
            or type(value['total_bytes']) is not int or not 0<value['total_bytes']<2**64
            or type(value['device_name']) is not str or not re.fullmatch(r'Intel[^\r\n]{0,240}',value['device_name'])
            or any(value[k] is not True for k in ('tls_preserved','canaries','unloaded')) or value['forwarded'] is not forwarded):
        raise ValueError('device-total native scope failed')
    return dict(total_bytes=value['total_bytes'],device_name=value['device_name'])
