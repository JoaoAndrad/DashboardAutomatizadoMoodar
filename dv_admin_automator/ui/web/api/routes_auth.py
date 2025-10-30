from fastapi import APIRouter ,HTTPException ,Request 
from fastapi .responses import JSONResponse 
import logging 
from ..import jobs 
from dv_admin_automator .browser .pool import get_default_pool 
router =APIRouter ()
logger =logging .getLogger ('dv_admin_automator.ui.web.api.routes_auth')
_SESSION_CREDENTIALS ={}
_PENDING_LOGINS ={}
@router .post ('/login')
async def login_endpoint (payload :dict ,request :Request ):
    username =payload .get ('username')
    password =payload .get ('password')
    headless =bool (payload .get ('headless',False ))
    if not username or not password :
        raise HTTPException (status_code =400 ,detail ='username and password required')
    try :
        pool =get_default_pool ()
        session_id =pool .create_session (headless =headless )
    except Exception :
        logging .getLogger ('dv_admin_automator.ui.web.api.routes_auth').exception ('failed creating browser session')
        session_id =None 
    try :
        if session_id :
            _SESSION_CREDENTIALS [session_id ]={'username':username ,'password':password ,'headless':headless }
    except Exception :
        logger .exception ('failed storing credentials in _SESSION_CREDENTIALS during login')
    jm =jobs .get_default_manager ()
    job_id =jm .submit (lambda :_login_job (session_id ,username ,password ,headless ))
    try :
        _PENDING_LOGINS [job_id ]={'username':username ,'password':password ,'session_id':session_id ,'success':None ,'message':None }
    except Exception :
        logger .exception ('failed registering pending login')
    resp ={'ok':True ,'job_id':job_id }
    if session_id :
        resp ['browser_session_id']=session_id 
    return JSONResponse (resp )
@router .post ('/login/complete')
async def complete_login (payload :dict ,request :Request ):
    job_id =payload .get ('job_id')if isinstance (payload ,dict )else None 
    if not job_id :
        raise HTTPException (status_code =400 ,detail ='job_id required')
    pending =_PENDING_LOGINS .get (job_id )
    if not pending :
        raise HTTPException (status_code =404 ,detail ='pending login not found')
    jm =jobs .get_default_manager ()
    st =jm .status (job_id )
    if not st or not st .get ('done'):
        raise HTTPException (status_code =400 ,detail ='job not finished')
    if not pending .get ('success'):
        raise HTTPException (status_code =400 ,detail ='login failed or not confirmed')
    username =pending .get ('username')
    password =pending .get ('password')
    session_id =pending .get ('session_id')
    session_written =False 
    try :
        request .session ['moodar_username']=username 
        request .session ['moodar_password']=password 
        session_written =True 
    except Exception :
        logger .exception ('failed storing credentials in session during complete_login')
    try :
        if session_id :
            _SESSION_CREDENTIALS [session_id ]={'username':username ,'password':password }
    except Exception :
        logger .exception ('failed storing credentials in _SESSION_CREDENTIALS during complete_login')
    try :
        del _PENDING_LOGINS [job_id ]
    except Exception :
        pass 
    resp ={'ok':True }
    if session_id :
        resp ['browser_session_id']=session_id 
    response =JSONResponse (resp )
    if not session_written :
        try :
            response .set_cookie ('moodar_logged_in','1',httponly =True )
        except Exception :
            logger .exception ('failed setting fallback login cookie in complete_login')
    return response 
@router .get ('/jobs/{job_id}')
async def job_status (job_id :str ):
    jm =jobs .get_default_manager ()
    st =jm .status (job_id )
    if st is None :
        return JSONResponse ({'ok':False ,'error':'not found'},status_code =404 )
    return JSONResponse ({'ok':True ,'status':st })
@router .get ('/session')
async def debug_session (request :Request ):
    try :
        sess =dict (request .session .items ())if hasattr (request ,'session')else None 
    except Exception :
        sess =None 
    cookies ={k :v for k ,v in request .cookies .items ()}if request .cookies else {}
    return JSONResponse ({'ok':True ,'session':sess ,'cookies':cookies })
def _login_job (session_id :str ,username :str ,password :str ,headless :bool =False ):
    try :
        from dv_admin_automator .browser .pool import get_default_pool 
        pool =get_default_pool ()
        mgr =None 
        if session_id :
            mgr =pool .get_manager (session_id )
        if not mgr :
            from dv_admin_automator .browser .manager import BrowserManager 
            bm =BrowserManager (headless =headless )
            driver =bm .start ()
        else :
            driver =mgr .driver 
        from selenium .webdriver .common .by import By 
        from selenium .webdriver .support .ui import WebDriverWait 
        from selenium .webdriver .support import expected_conditions as EC 
        import time 
        url ='https://webapp.moodar.com.br/moodashboard/'
        logging .getLogger ('dv_admin_automator.ui.web.api.routes_auth').info ('Starting login job for session %s (headless=%s)',session_id ,headless )
        wait =WebDriverWait (driver ,15 )
        driver .get (url )
        time .sleep (1 )
        username_selector ="input[type='text'], input[name='username'], input[name='user'], input[id*='username'], input[id*='user'], input[placeholder*='usuário'], input[placeholder*='username']"
        password_selector ="input[type='password'], input[name='password'], input[id*='password'], input[placeholder*='senha']"
        u_field =wait .until (EC .presence_of_element_located ((By .CSS_SELECTOR ,username_selector )))
        p_field =driver .find_element (By .CSS_SELECTOR ,password_selector )
        u_field .clear ();u_field .send_keys (username )
        p_field .clear ();p_field .send_keys (password )
        try :
            login_btn =driver .find_element (By .CSS_SELECTOR ,"button[type='submit'], input[type='submit'], button[class*='login'], button[class*='entrar']")
            login_btn .click ()
            logging .getLogger ('dv_admin_automator.ui.web.api.routes_auth').info ('Clicked login button for session %s',session_id )
        except Exception :
            logger .exception ('Login button not found or click failed')
        time .sleep (3 )
        success =False 
        message =None 
        try :
            try :
                cur =driver .execute_script ('return document.location.href;')
            except Exception :
                cur =None 
            dashboard_prefix ='https://webapp.moodar.com.br/moodashboard/'
            if cur and isinstance (cur ,str )and cur .startswith (dashboard_prefix ):
                success =True 
            else :
                possible =["button.logout","a.logout","[data-logged-in='true']","nav"]
                for sel in possible :
                    try :
                        el =driver .find_elements (By .CSS_SELECTOR ,sel )
                        if el and len (el )>0 :
                            success =True 
                            break 
                    except Exception :
                        continue 
        except Exception :
            logger .exception ('error while detecting login success')
        try :
            from ..jobs import get_current_job_id 
            jid =get_current_job_id ()
            if jid and jid in _PENDING_LOGINS :
                _PENDING_LOGINS [jid ]['success']=bool (success )
                _PENDING_LOGINS [jid ]['message']=message 
        except Exception :
            logger .exception ('failed updating pending login status')
        logger .info ('login job finished (session %s) success=%s',session_id ,success )
    except Exception :
        logger .exception ('login job failed')