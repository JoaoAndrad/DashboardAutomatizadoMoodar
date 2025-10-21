
from fastapi import APIRouter ,HTTPException ,Request ,Body 
from fastapi .responses import JSONResponse 
from pydantic import BaseModel 
from typing import List ,Optional 
from dv_admin_automator .browser .pool import get_default_pool 

router =APIRouter ()


class ScheduleCycleRequest (BaseModel ):
    participant_id :str 
    participant_name :Optional [str ]=None 
    therapist :str 
    plan :str 
    start_date :str 
    start_time :str 
    tipo :str 
    minutagem :str 
    quantidade :Optional [int ]=None 
    browser_session_id :Optional [str ]=None 

@router .post ('/api/appointments/schedule')
async def api_appointments_schedule (
req :ScheduleCycleRequest =Body (...)
):

    try :
        from dv_admin_automator .backend .appointments import schedule_cycle_appointments 
        mgr =None 
        chosen_sid =None 
        print (f"[api_appointments_schedule] browser_session_id: {req .browser_session_id }")
        pool =get_default_pool ()
        if req .browser_session_id :
            mgr =pool .get_manager (req .browser_session_id )
            if mgr :
                chosen_sid =req .browser_session_id 
            print (f"[api_appointments_schedule] mgr from pool: {mgr }")


        if mgr is None :
            try :
                try :
                    with getattr (pool ,'_lock'):
                        items =list (pool ._sessions .items ())
                except Exception :
                    items =list (getattr (pool ,'_sessions',{}).items ())
                chosen =None 
                for sid ,info in items :
                    try :
                        mgr_candidate =info .get ('manager')
                        if not mgr_candidate :
                            continue 
                        drv =getattr (mgr_candidate ,'driver',None )
                        if not drv :
                            continue 
                        url =None 
                        try :
                            url =drv .execute_script ('return document.location.href;')
                        except Exception :
                            try :
                                url =drv .current_url if hasattr (drv ,'current_url')else None 
                            except Exception :
                                url =None 
                        if url and ('/moodashboard'in url or '/participante'in url or '/import/'in url ):
                            chosen =(sid ,mgr_candidate )
                            break 
                        if not chosen :
                            chosen =(sid ,mgr_candidate )
                    except Exception :
                        continue 
                if chosen :
                    chosen_sid ,mgr =chosen [0 ],chosen [1 ]
                    print (f"[api_appointments_schedule] Using fallback browser session {chosen_sid } for scheduling")
            except Exception :
                mgr =None 


        if mgr is None :
            msg ='No active browser session available for scheduling. Perform search/history to create a session or provide browser_session_id.'
            print (f"[api_appointments_schedule] {msg }")
            return JSONResponse ({'ok':False ,'error':'no_active_browser_session','message':msg },status_code =400 )
        result =schedule_cycle_appointments (
        participant_id =req .participant_id ,
        participant_name =req .participant_name ,
        therapist =req .therapist ,
        plan =req .plan ,
        start_date =req .start_date ,
        start_time =req .start_time ,
        tipo =req .tipo ,
        minutagem =req .minutagem ,
        quantidade =req .quantidade ,
        manager =mgr 
        )
        return JSONResponse (result )
    except Exception as e :
        print (f"[api_appointments_schedule] Exception: {e }")
        return JSONResponse ({'ok':False ,'error':str (e )},status_code =500 )


@router .get ('/api/appointments/history')
async def api_appointments_history (
participant :str =None ,
participant_id :str =None ,
participant_name :str =None ,
browser_session_id :str =None 
):
    try :
        from dv_admin_automator .backend .appointments import search_participant_rows 
        mgr =None 

        if browser_session_id :
            try :
                pool =get_default_pool ()
                mgr =pool .get_manager (browser_session_id )
            except Exception :
                mgr =None 
            if mgr is None :
                try :
                    try :
                        with getattr (pool ,'_lock'):
                            items =list (pool ._sessions .items ())
                    except Exception :
                        items =list (getattr (pool ,'_sessions',{}).items ())
                    for sid ,info in items :
                        try :
                            if sid ==browser_session_id :
                                mgr =info .get ('manager')
                                break 
                        except Exception :
                            continue 
                except Exception :
                    mgr =None 
        if not browser_session_id and mgr is None :
            try :
                pool =get_default_pool ()
                try :
                    with getattr (pool ,'_lock'):
                        items =list (pool ._sessions .items ())
                except Exception :
                    items =list (getattr (pool ,'_sessions',{}).items ())
                chosen =None 
                for sid ,info in items :
                    try :
                        mgr_candidate =info .get ('manager')
                        if not mgr_candidate :
                            continue 
                        drv =getattr (mgr_candidate ,'driver',None )
                        if not drv :
                            continue 
                        url =None 
                        try :
                            url =drv .execute_script ('return document.location.href;')
                        except Exception :
                            try :
                                url =drv .current_url if hasattr (drv ,'current_url')else None 
                            except Exception :
                                url =None 
                        if url and ('/moodashboard'in url or '/participante'in url or '/import/'in url ):
                            chosen =(sid ,mgr_candidate )
                            break 
                        if not chosen :
                            chosen =(sid ,mgr_candidate )
                    except Exception :
                        continue 
                if chosen :
                    browser_session_id ,mgr =chosen [0 ],chosen [1 ]
                    print (f"Using fallback browser session {browser_session_id } for appointments search")
            except Exception :
                mgr =None 
        if browser_session_id and mgr is None :
            msg =f"Requested browser_session_id='{browser_session_id }' has no active session"
            print (msg )
            try :
                from dv_admin_automator .ui .web .api import routes_auth 
                creds =routes_auth ._SESSION_CREDENTIALS .get (browser_session_id )
            except Exception :
                creds =None 
            if creds and isinstance (creds ,dict ):
                try :
                    pool =get_default_pool ()
                    headless =bool (creds .get ('headless',False ))
                    new_sid =pool .create_session (headless =headless )
                    from dv_admin_automator .ui .web .api import routes_auth as auth_routes 
                    from dv_admin_automator import jobs 
                    jm =jobs .get_default_manager ()
                    job_id =jm .submit (lambda :auth_routes ._login_job (new_sid ,creds .get ('username'),creds .get ('password'),headless ))
                    return JSONResponse ({
                    'ok':True ,
                    'message':'scheduled_login_for_missing_session',
                    'browser_session_id':new_sid ,
                    'job_id':job_id 
                    })
                except Exception as e :
                    return JSONResponse ({
                    'ok':False ,
                    'error':'no_active_browser_session',
                    'message':msg ,
                    'browser_session_id':browser_session_id ,
                    'scheduling_error':str (e )
                    },status_code =500 )
            return JSONResponse ({
            'ok':False ,
            'error':'no_active_browser_session',
            'message':msg ,
            'browser_session_id':browser_session_id 
            },status_code =404 )


        if participant_id :
            try :
                from dv_admin_automator .backend .appointments import get_participant_history 
                history =get_participant_history (participant_id ,manager =mgr )
                if not history :
                    return JSONResponse ({'ok':False ,'error':'no_history','message':'Nenhum histórico encontrado.'},status_code =404 )
                return JSONResponse ({'ok':True ,**history })
            except Exception as e :
                return JSONResponse ({'ok':False ,'error':str (e )},status_code =500 )


        if not participant :
            return JSONResponse ({'ok':False ,'error':'participant required'},status_code =400 )
        rows =search_participant_rows (participant ,manager =mgr )
        return JSONResponse ({'ok':True ,'participants':rows })
    except Exception as e :
        return JSONResponse ({'ok':False ,'error':str (e )},status_code =500 )
