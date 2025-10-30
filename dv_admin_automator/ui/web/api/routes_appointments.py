from fastapi import APIRouter ,HTTPException ,Request ,Body 
from fastapi .responses import JSONResponse 
from pydantic import BaseModel 
from typing import List ,Optional 
from dv_admin_automator .browser .pool import get_default_pool 
import asyncio 
_history_inflight ={}
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
        resolved_participant_id =req .participant_id 
        resolved_participant_name =req .participant_name 
        try :
            if resolved_participant_id and ('@'in str (resolved_participant_id )or not str (resolved_participant_id ).strip ().isdigit ()):
                try :
                    from dv_admin_automator .backend .appointments import search_participant_rows 
                    rows =search_participant_rows (resolved_participant_id ,manager =mgr )
                    if rows :
                        match =None 
                        for r in rows :
                            if r .get ('email')and r .get ('email').lower ()==str (resolved_participant_id ).lower ():
                                match =r 
                                break 
                        if match is None :
                            match =rows [0 ]
                        if match :
                            resolved_participant_id =str (match .get ('id')or match .get ('patient_id')or resolved_participant_id )
                            resolved_participant_name =resolved_participant_name or match .get ('name')
                            print (f"[api_appointments_schedule] Resolved participant_id '{req .participant_id }' -> '{resolved_participant_id }' (name='{resolved_participant_name }')")
                except Exception as e :
                    print (f"[api_appointments_schedule] participant_id resolution failed: {e }")
        except Exception :
            pass 
        result =schedule_cycle_appointments (
        participant_id =resolved_participant_id ,
        participant_name =resolved_participant_name ,
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
email :str =None ,
participant_name :str =None ,
browser_session_id :str =None ,
for_schedule :bool =False 
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
        if for_schedule :
            try :
                if participant_id :
                    rows =search_participant_rows (participant_id ,manager =mgr )
                    return JSONResponse ({'ok':True ,'participants':rows })
                if participant :
                    rows =search_participant_rows (participant ,manager =mgr )
                    return JSONResponse ({'ok':True ,'participants':rows })
                return JSONResponse ({'ok':False ,'error':'no_query','message':'Provide participant or participant_id for schedule lookup.'},status_code =400 )
            except Exception as e :
                return JSONResponse ({'ok':False ,'error':str (e )},status_code =500 )
        try :
            from dv_admin_automator .backend .appointments import get_participant_history ,search_participant_rows 
            if email :
                try :
                    loop =asyncio .get_running_loop ()
                    if email in _history_inflight :
                        print (f"[api_appointments_history] awaiting existing in-flight history request for {email }")
                        history =await _history_inflight [email ]
                    else :
                        fut =loop .create_future ()
                        _history_inflight [email ]=fut 
                        try :
                            history =await loop .run_in_executor (None ,lambda :get_participant_history (email ,manager =mgr ))
                            fut .set_result (history )
                        except Exception as e :
                            fut .set_exception (e )
                            raise 
                        finally :
                            _history_inflight .pop (email ,None )
                except Exception as e :
                    print (f"[api_appointments_history] error fetching history by email: {e }")
                    history =None 
                if history and isinstance (history ,dict )and history .get ('appointments')and len (history .get ('appointments'))>0 :
                    return JSONResponse ({'ok':True ,**history })
                return JSONResponse ({'ok':False ,'error':'no_history','message':'Nenhum appointment encontrado para o e-mail fornecido.'},status_code =404 )
            search_query =None 
            if participant_id :
                try :
                    rows =search_participant_rows (participant_id ,manager =mgr )
                    if rows :
                        candidate =None 
                        for r in rows :
                            if str (r .get ('id','')).strip ()and str (r .get ('id','')).strip ()==str (participant_id ).strip ():
                                candidate =r ;break 
                        if candidate is None :
                            candidate =rows [0 ]
                        if candidate and candidate .get ('email'):
                            search_query =candidate .get ('email')
                except Exception :
                    search_query =None 
            if not search_query and participant :
                try :
                    rows =search_participant_rows (participant ,manager =mgr )
                    if rows and rows [0 ].get ('email'):
                        search_query =rows [0 ].get ('email')
                except Exception :
                    search_query =None 
            if search_query :
                try :
                    loop =asyncio .get_running_loop ()
                    if search_query in _history_inflight :
                        print (f"[api_appointments_history] awaiting existing in-flight history request for {search_query }")
                        history =await _history_inflight [search_query ]
                    else :
                        fut =loop .create_future ()
                        _history_inflight [search_query ]=fut 
                        try :
                            history =await loop .run_in_executor (None ,lambda :get_participant_history (search_query ,manager =mgr ))
                            fut .set_result (history )
                        except Exception as e :
                            fut .set_exception (e )
                            raise 
                        finally :
                            _history_inflight .pop (search_query ,None )
                except Exception :
                    history =None 
                if history :
                    return JSONResponse ({'ok':True ,**history })
                return JSONResponse ({'ok':False ,'error':'no_history','message':'Nenhum histórico encontrado para o termo de busca.'},status_code =404 )
        except Exception as e :
            return JSONResponse ({'ok':False ,'error':str (e )},status_code =500 )
        if not participant :
            return JSONResponse ({'ok':False ,'error':'participant required'},status_code =400 )
        rows =search_participant_rows (participant ,manager =mgr )
        return JSONResponse ({'ok':True ,'participants':rows })
    except Exception as e :
        return JSONResponse ({'ok':False ,'error':str (e )},status_code =500 )