import time 
import threading 
from typing import Optional ,Dict ,Any 
_CACHE_LOCK =threading .Lock ()
_CACHE :Dict [str ,Any ]={
'service_account_info':None ,
'expires_at':0 ,
}
def set_service_account_info (info :Dict [str ,Any ],ttl :int =900 ):
    with _CACHE_LOCK :
        _CACHE ['service_account_info']=info 
        _CACHE ['expires_at']=int (time .time ())+int (ttl )
def get_service_account_info ()->Optional [Dict [str ,Any ]]:
    with _CACHE_LOCK :
        expires =_CACHE .get ('expires_at',0 )
        if expires and time .time ()<expires :
            return _CACHE .get ('service_account_info')
        _CACHE ['service_account_info']=None 
        _CACHE ['expires_at']=0 
        return None 
def clear_service_account_info ():
    with _CACHE_LOCK :
        _CACHE ['service_account_info']=None 
        _CACHE ['expires_at']=0 