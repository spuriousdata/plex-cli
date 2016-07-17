def s2d(kv):
    """Turn a string k=v1,k2=v2 into a dict"""
    return dict([s.split('=') for s in kv.split(",")])
