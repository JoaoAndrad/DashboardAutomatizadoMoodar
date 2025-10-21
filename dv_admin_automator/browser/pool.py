import threading 
import time 
import uuid 
import logging 
from typing import Optional ,Dict 

from .manager import BrowserManager 

logger =logging .getLogger ('dv_admin_automator.browser.pool')


class BrowserPool :

    def __init__ (self ):
        self ._lock =threading .Lock ()
        self ._sessions :Dict [str ,Dict ]={}

    def create_session (self ,headless :bool =True ,window :str ='1920x1080')->str :
        bm =BrowserManager (headless =headless ,window =window )
        driver =bm .start ()
        sess =uuid .uuid4 ().hex 
        with self ._lock :
            self ._sessions [sess ]={'manager':bm ,'created_at':time .time ()}
        logger .info ('created browser session %s (headless=%s)',sess ,headless )
        return sess 

    def get_manager (self ,session_id :str )->Optional [BrowserManager ]:
        with self ._lock :
            info =self ._sessions .get (session_id )
            if not info :
                return None 
            return info .get ('manager')

    def close_session (self ,session_id :str )->bool :
        with self ._lock :
            info =self ._sessions .pop (session_id ,None )
        if not info :
            return False 
        try :
            mgr :BrowserManager =info .get ('manager')
            mgr .quit ()
        except Exception :
            logger .exception ('error closing session %s',session_id )
        logger .info ('closed session %s',session_id )
        return True 



_default_pool :Optional [BrowserPool ]=None 


def get_default_pool ()->BrowserPool :
    global _default_pool 
    if _default_pool is None :
        _default_pool =BrowserPool ()
    return _default_pool 
