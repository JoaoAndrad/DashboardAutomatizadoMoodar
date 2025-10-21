from fastapi import APIRouter ,UploadFile ,File ,HTTPException ,BackgroundTasks 
from fastapi .responses import JSONResponse 
import os 
import uuid 
from typing import Any ,Dict 

from ..jobs import get_default_manager 
from dv_admin_automator .backend .importer .service import get_default_import_service 




_UPLOAD_DIR =os .path .join (os .getcwd (),'tmp_uploads')
os .makedirs (_UPLOAD_DIR ,exist_ok =True )

router =APIRouter (prefix ="/api/import",tags =["import"])


_JOB_LOGS ={}


def _append_log (job_id :str ,line :str ):
    lst =_JOB_LOGS .setdefault (job_id ,[])
    lst .append (line )


@router .post ('/start')
async def start_import (payload :Dict [str ,Any ]):

    upload_id =payload .get ('upload_id')
    if not upload_id :
        raise HTTPException (status_code =400 ,detail ='upload_id required')
    path =os .path .join (_UPLOAD_DIR ,upload_id )
    if not os .path .exists (path ):
        raise HTTPException (status_code =404 ,detail ='upload not found')

    headless =bool (payload .get ('headless',True ))
    minimized =bool (payload .get ('minimized',False ))
    company_name =payload .get ('company_name')or ''
    browser_session_id =payload .get ('browser_session_id')
    import_type =payload .get ('import_type','auto')

    service =get_default_import_service ()


    public_job_id ='import:'+uuid .uuid4 ().hex [:10 ]
    _JOB_LOGS [public_job_id ]=[f'Import requested for {upload_id }']


    def append_fn (jid ,msg ):
        _JOB_LOGS .setdefault (jid ,[]).append (msg )

    service .start_import (path ,public_job_id ,append_fn ,headless =headless ,minimized =minimized ,company_name =company_name ,browser_session_id =browser_session_id ,import_type =import_type )
    return JSONResponse ({"ok":True ,"job_id":public_job_id })


@router .get ('/{job_id}/status')
async def import_status (job_id :str ):
    manager =get_default_manager ()

    service =get_default_import_service ()
    internal =None 
    try :
        internal =service .get_internal_job_id (job_id )
    except Exception :
        internal =None 

    lookup_id =internal or job_id 
    st =manager .status (lookup_id )
    if st is None :




        import re 
        def _sanitize (s :str )->str :
            return re .sub (r'[^A-Za-z0-9_.-]','_',s or '')
        safe_job =_sanitize (job_id )
        found_marker =False 
        try :
            for fname in os .listdir (_UPLOAD_DIR ):
                if fname .endswith ('.awaiting_confirm')and safe_job in fname :
                    found_marker =True 
                    break 
        except Exception :
            found_marker =False 

        if found_marker :
            st ={'done':True ,'cancelled':False ,'exception':None ,'awaiting_confirmation':True }
        else :
            raise HTTPException (status_code =404 ,detail ='job not found')
    return JSONResponse ({"ok":True ,"status":st })


@router .get ('/{job_id}/logs')
async def import_logs (job_id :str ):
    logs =_JOB_LOGS .get (job_id ,[])
    return JSONResponse ({"ok":True ,"logs":logs })


@router .post ('/{job_id}/confirm')
async def import_confirm (job_id :str ,background :BackgroundTasks ):

    import json 
    import re 
    from dv_admin_automator .backend .importer import runner as import_runner 


    def _sanitize (s :str )->str :
        return re .sub (r'[^A-Za-z0-9_.-]','_',s or '')

    safe_job =_sanitize (job_id )

    cand =None 
    try :
        for fname in os .listdir (_UPLOAD_DIR ):
            if fname .endswith ('.awaiting_confirm')and safe_job in fname :
                cand =os .path .join (_UPLOAD_DIR ,fname )
                break 
    except Exception :
        cand =None 


    if not cand :
        logs =_JOB_LOGS .get (job_id ,[])
        for line in logs :
            if 'marker='in line and '.awaiting_confirm'in line :

                try :
                    part =line .split ('marker=')[-1 ].strip ()

                    if (part .startswith ('"')and part .endswith ('"'))or (part .startswith ("'")and part .endswith ("'")):
                        part =part [1 :-1 ]
                    if os .path .exists (part ):
                        cand =part 
                        break 
                except Exception :
                    continue 


    if not cand :
        try :
            for fname in os .listdir (_UPLOAD_DIR ):
                if not fname .endswith ('.awaiting_confirm'):
                    continue 
                path =os .path .join (_UPLOAD_DIR ,fname )
                try :
                    with open (path ,'r',encoding ='utf-8')as fh :
                        meta =json .load (fh )
                    tmp_path =meta .get ('tmp_path')or ''
                    b =os .path .basename (str (tmp_path ))
                    if not b :
                        continue 

                    if safe_job in b or (job_id and job_id .replace (':','_')in b )or (job_id .split ('_')[0 ]in b ):
                        cand =path 
                        break 
                except Exception :
                    continue 
        except Exception :
            cand =None 

    if not cand :
        raise HTTPException (status_code =404 ,detail ='awaiting confirmation marker not found')

    try :
        with open (cand ,'r',encoding ='utf-8')as fh :
            meta =json .load (fh )
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =f'failed to read marker: {e }')

    tmp_path =meta .get ('tmp_path')
    session_id =meta .get ('session_id')


    def append_fn (jid ,msg ):
        _JOB_LOGS .setdefault (jid ,[]).append (msg )

    if not session_id :



        try :
            from dv_admin_automator .browser .pool import get_default_pool 
            pool =get_default_pool ()
            chosen =None 



            try :
                with getattr (pool ,'_lock'):
                    items =list (pool ._sessions .items ())
            except Exception :
                items =list (getattr (pool ,'_sessions',{}).items ())

            for sid ,info in items :
                try :
                    mgr =info .get ('manager')
                    if not mgr :
                        continue 

                    url =None 
                    try :
                        drv =getattr (mgr ,'driver',None )or mgr .start ()
                        url =drv .current_url if hasattr (drv ,'current_url')else None 
                    except Exception :
                        url =None 
                    if url and ('/moodashboard'in url or '/import/'in url ):
                        chosen =sid 
                        break 
                    if not chosen :
                        chosen =sid 
                except Exception :
                    continue 
            if chosen :
                session_id =chosen 
                _JOB_LOGS .setdefault (job_id ,[]).append (f'[system] using fallback browser session {chosen } for confirmation')
        except Exception :
            session_id =None 

        if not session_id :

            raise HTTPException (status_code =400 ,detail ='no browser session available to confirm')


    def _bg_confirm (marker_path :str ,sid :str ,jid :str ):
        try :
            append =lambda a ,b :_JOB_LOGS .setdefault (jid ,[]).append (b )
            ok_local =import_runner .confirm_import_session (sid ,jid ,append )
            if ok_local :
                try :
                    os .remove (marker_path )
                except Exception :
                    pass 
                try :
                    service =get_default_import_service ()
                    internal =service .get_internal_job_id (jid )
                    if internal :
                        jm =get_default_manager ()
                        jm .set_awaiting_confirmation (internal ,False )
                        _JOB_LOGS .setdefault (jid ,[]).append (f'[system] cleared awaiting_confirmation for internal {internal }')
                except Exception :
                    pass 
                _JOB_LOGS .setdefault (jid ,[]).append ('[system] confirmation completed (background)')
            else :
                _JOB_LOGS .setdefault (jid ,[]).append ('[system] confirmation failed (background)')
        except Exception as e :
            _JOB_LOGS .setdefault (jid ,[]).append (f'[system] background confirm exception: {e }')


    background .add_task (_bg_confirm ,cand ,session_id ,job_id )
    _JOB_LOGS .setdefault (job_id ,[]).append ('[system] confirmation scheduled (background)')
    return JSONResponse ({"ok":True ,"confirmed":"scheduled"})


@router .post ('/{job_id}/cancel')
async def import_cancel (job_id :str ):

    import json 
    import re 


    def _sanitize (s :str )->str :
        return re .sub (r'[^A-Za-z0-9_.-]','_',s or '')

    safe_job =_sanitize (job_id )
    cand =None 
    for fname in os .listdir (_UPLOAD_DIR ):
        if fname .endswith ('.awaiting_confirm')and safe_job in fname :
            cand =os .path .join (_UPLOAD_DIR ,fname )
            break 

    if cand and os .path .exists (cand ):
        try :

            try :
                with open (cand +'.canceled','w',encoding ='utf-8')as fh :
                    fh .write ('canceled')
            except Exception :
                pass 
            os .remove (cand )
        except Exception :
            pass 


    _JOB_LOGS .setdefault (job_id ,[]).append ('[system] import canceled by operator')


    try :
        service =get_default_import_service ()
        internal =service .get_internal_job_id (job_id )
        if internal :
            jm =get_default_manager ()
            jm .set_awaiting_confirmation (internal ,False )
            _JOB_LOGS .setdefault (job_id ,[]).append (f'[system] cleared awaiting_confirmation for internal {internal } (canceled)')
    except Exception :
        pass 

    return JSONResponse ({"ok":True ,"canceled":True })


@router .get ('/{job_id}/debug')
async def import_debug (job_id :str ):

    import re ,json 
    from ..jobs import get_default_manager 
    service =get_default_import_service ()
    internal =None 
    try :
        internal =service .get_internal_job_id (job_id )
    except Exception :
        internal =None 

    jm =get_default_manager ()
    status =None 
    if internal :
        status =jm .status (internal )
    else :

        status =jm .status (job_id )


    def _sanitize (s :str )->str :
        return re .sub (r'[^A-Za-z0-9_.-]','_',s or '')
    safe_job =_sanitize (job_id )
    markers =[]
    for fname in os .listdir (_UPLOAD_DIR ):
        if fname .endswith ('.awaiting_confirm')and safe_job in fname :
            path =os .path .join (_UPLOAD_DIR ,fname )
            try :
                with open (path ,'r',encoding ='utf-8')as fh :
                    meta =json .load (fh )
            except Exception as e :
                meta ={'error':str (e )}
            markers .append ({'path':path ,'meta':meta })

    logs =_JOB_LOGS .get (job_id ,[])
    return JSONResponse ({'ok':True ,'job_id':job_id ,'internal':internal ,'status':status ,'logs':logs ,'markers':markers })


def _save_upload_to_disk (upload :UploadFile )->str :
    upload_id =uuid .uuid4 ().hex 
    filename =f"{upload_id }_{os .path .basename (upload .filename or 'upload')}"
    dest =os .path .join (_UPLOAD_DIR ,filename )
    with open (dest ,'wb')as f :
        while True :
            chunk =upload .file .read (1024 *64 )
            if not chunk :
                break 
            f .write (chunk )
    return dest 


@router .post ('/upload')
async def upload_and_preview (file :UploadFile =File (...))->Any :
    if not file .filename :
        raise HTTPException (status_code =400 ,detail ='Missing filename')

    dest =_save_upload_to_disk (file )


    try :
        from dv_admin_automator .backend .importer .detector import detect_file_type 
    except Exception as e :

        try :
            from dv_admin_automator .backend .importer .parsers import parse_preview as _parse_preview 
            preview =_parse_preview (dest ,rows =5 )
            upload_id =os .path .basename (dest )
            return JSONResponse ({"ok":True ,"upload_id":upload_id ,"preview":preview })
        except Exception as e2 :
            raise HTTPException (status_code =500 ,detail =f'Detector/parser unavailable: {e } / {e2 }')

    try :
        detection =detect_file_type (dest ,sample_rows =5 )
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =f'Failed to detect uploaded file: {e }')

    upload_id =os .path .basename (dest )

    return JSONResponse ({"ok":True ,"upload_id":upload_id ,"preview":detection .get ('preview',{}),"detection":{k :v for k ,v in detection .items ()if k !='preview'}})
