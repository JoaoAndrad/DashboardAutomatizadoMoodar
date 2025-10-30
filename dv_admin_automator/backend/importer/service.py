import time 
import os 
from typing import Optional ,Dict ,Any 
from ...ui .web .jobs import get_default_manager 
class ImportService :
    def __init__ (self ):
        self .manager =get_default_manager ()
        self ._public_to_internal ={}
    def start_import (self ,upload_path :str ,job_id :str ,log_append_fn ,*,headless :bool =True ,minimized :bool =False ,company_name :str ='',company_id :Optional [str ]=None ,browser_session_id :Optional [str ]=None ,import_type :str ='auto')->str :
        def _job ():
            log_append_fn (job_id ,'job started - handover to legacy adapter')
            try :
                from .legacy_adapter import run_import_full 
            except Exception as e :
                log_append_fn (job_id ,f'failed to import legacy_adapter: {e }')
                return {"success":False ,"error":str (e )}
            try :
                ok =run_import_full (upload_path ,job_id ,log_append_fn ,
                browser_session_id =browser_session_id ,
                headless =headless ,minimized =minimized ,
                company_name =company_name or '',
                company_id =company_id ,
                import_type =import_type )
                if ok :
                    log_append_fn (job_id ,'legacy adapter import finished successfully')
                    return {"success":True }
                else :
                    log_append_fn (job_id ,'legacy adapter reported failure')
                    return {"success":False }
            finally :
                try :
                    from pathlib import Path 
                    base =Path .cwd ()/'tmp_uploads'
                    target =Path (upload_path ).resolve ()
                    try :
                        base_res =base .resolve ()
                    except Exception :
                        base_res =base 
                    if str (target ).startswith (str (base_res ))and target .exists ():
                        try :
                            target .unlink ()
                            log_append_fn (job_id ,f'deleted uploaded file: {target .name }')
                        except Exception as e :
                            log_append_fn (job_id ,f'failed to delete uploaded file {target .name }: {e }')
                except Exception :
                    log_append_fn (job_id ,'cleanup: unexpected error during upload removal')
        internal_id =self .manager .submit (_job )
        try :
            self ._public_to_internal [job_id ]=internal_id 
        except Exception :
            pass 
        return job_id 
    def get_internal_job_id (self ,public_job_id :str ):
        return self ._public_to_internal .get (public_job_id )
_default_service :Optional [ImportService ]=None 
def get_default_import_service ()->ImportService :
    global _default_service 
    if _default_service is None :
        _default_service =ImportService ()
    return _default_service 