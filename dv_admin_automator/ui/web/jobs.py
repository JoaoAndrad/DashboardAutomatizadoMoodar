import concurrent .futures 
import threading 
import secrets 
import time 
from typing import Callable ,Dict ,Optional 
import logging 
import threading as _threading 
logger =logging .getLogger ('dv_admin_automator.ui.web.jobs')
class JobManager :
    def __init__ (self ,max_workers :int =2 ):
        self ._executor =concurrent .futures .ThreadPoolExecutor (max_workers =max_workers )
        self ._jobs :Dict [str ,Dict ]={}
        self ._lock =threading .Lock ()
    def submit (self ,fn :Callable ,*args ,**kwargs )->str :
        job_id =secrets .token_urlsafe (8 )
        def _wrapper ():
            try :
                _thread_local .current_job_id =job_id 
            except Exception :
                pass 
            logger .info ('job %s started',job_id )
            try :
                res =fn (*args ,**kwargs )
                logger .info ('job %s finished',job_id )
                return res 
            except Exception :
                logger .exception ('job %s raised',job_id )
                raise 
        future =self ._executor .submit (_wrapper )
        with self ._lock :
            self ._jobs [job_id ]={'future':future ,'submitted_at':time .time (),'awaiting_confirmation':False }
        return job_id 
    def status (self ,job_id :str )->Optional [Dict ]:
        with self ._lock :
            info =self ._jobs .get (job_id )
            if not info :
                return None 
            future =info ['future']
            return {
            'done':future .done (),
            'cancelled':future .cancelled (),
            'exception':None if not future .done ()else (str (future .exception ())if future .exception ()else None ),
            'awaiting_confirmation':bool (info .get ('awaiting_confirmation',False )),
            }
    def set_awaiting_confirmation (self ,job_id :str ,value :bool =True )->bool :
        with self ._lock :
            info =self ._jobs .get (job_id )
            if not info :
                return False 
            info ['awaiting_confirmation']=bool (value )
            return True 
_default :Optional [JobManager ]=None 
def get_default_manager ()->JobManager :
    global _default 
    if _default is None :
        _default =JobManager ()
    return _default 
_thread_local =_threading .local ()
def get_current_job_id ()->Optional [str ]:
    try :
        return getattr (_thread_local ,'current_job_id',None )
    except Exception :
        return None 