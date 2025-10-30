from fastapi import APIRouter ,Query ,HTTPException ,Request 
from fastapi .responses import JSONResponse 
from typing import List ,Dict 
import os 
import json 
import time 
import uuid 
import datetime 
import logging 
import tempfile 
from ..jobs import get_default_manager 
from dv_admin_automator .browser .pool import get_default_pool 
router =APIRouter ()
_COMPANY_JOB_LOGS :Dict [str ,List [str ]]={}
_PUBLIC_TO_INTERNAL :Dict [str ,str ]={}
@router .get ('/api/companies')
async def api_companies (q :str =Query ('',description ='Query string to search companies')):
    cwd =os .getcwd ()
    files =[f for f in os .listdir (cwd )if f .startswith ('companies_cache_')and f .endswith ('.json')]
    if not files :
        return JSONResponse ([])
    files .sort (reverse =True )
    latest =files [0 ]
    try :
        with open (os .path .join (cwd ,latest ),'r',encoding ='utf-8')as fh :
            data =json .load (fh )
            if isinstance (data ,list ):
                def _with_url (c ):
                    cid =c .get ('id')
                    try :
                        url =f"/admin/corporate/company/{cid }/change/"if cid is not None else ''
                    except Exception :
                        url =''
                    new =dict (c )
                    new ['url']=url 
                    return new 
                transformed =[_with_url (c )for c in data ]
                if q :
                    ql =q .lower ()
                    return JSONResponse ([c for c in transformed if ql in c .get ('name','').lower ()or ql in str (c .get ('id',''))])
                return JSONResponse (transformed )
    except Exception :
        return JSONResponse ([])
    return JSONResponse ([])
@router .post ('/api/companies/refresh')
async def api_companies_refresh (request :Request ):
    payload =await request .json ()
    username =payload .get ('username')
    password =payload .get ('password')
    headless =bool (payload .get ('headless',False ))
    browser_session_id =payload .get ('browser_session_id')
    public_job_id ='companies_refresh:'+uuid .uuid4 ().hex [:10 ]
    _COMPANY_JOB_LOGS [public_job_id ]=[]
    try :
        if (not username or not password )and browser_session_id :
            try :
                from .routes_auth import _SESSION_CREDENTIALS 
                creds =_SESSION_CREDENTIALS .get (browser_session_id )
                if creds :
                    username =username or creds .get ('username')
                    password =password or creds .get ('password')
                    _COMPANY_JOB_LOGS [public_job_id ].append ('[companies] using in-memory credentials mapped to browser_session_id')
            except Exception :
                pass 
        if (not username or not password )and hasattr (request ,'session'):
            try :
                suser =request .session .get ('moodar_username')
                spass =request .session .get ('moodar_password')
                if suser and spass :
                    username =username or suser 
                    password =password or spass 
                    _COMPANY_JOB_LOGS [public_job_id ].append ('[companies] using session-stored credentials')
            except Exception :
                pass 
        if (not username or not password )and browser_session_id :
            try :
                from .routes_auth import _SESSION_CREDENTIALS 
                creds =_SESSION_CREDENTIALS .get (browser_session_id )
                if creds :
                    username =username or creds .get ('username')
                    password =password or creds .get ('password')
                    _COMPANY_JOB_LOGS [public_job_id ].append ('[companies] using fallback in-memory credentials')
            except Exception :
                pass 
    except Exception :
        pass 
    if not username or not password :
        raise HTTPException (status_code =400 ,detail ='username and password required')
    jm =get_default_manager ()
    _COMPANY_JOB_LOGS [public_job_id ].append (f'Companies refresh requested by {username }')
    def _append (msg :str ):
        try :
            _COMPANY_JOB_LOGS .setdefault (public_job_id ,[]).append (msg )
        except Exception :
            pass 
    def _job ():
        try :
            _append ('[companies] starting refresh job')
            logging .getLogger ('dv_admin_automator.ui.web.api.routes_companies').info ('Companies refresh job %s starting (headless=%s)',public_job_id ,headless )
            pool =get_default_pool ()
            _append ('[companies] creating browser session (visible for now)')
            logging .getLogger ('dv_admin_automator.ui.web.api.routes_companies').info ('Creating browser session for companies refresh %s',public_job_id )
            session =pool .create_session (headless =headless )
            mgr =pool .get_manager (session )
            if not mgr or not getattr (mgr ,'driver',None ):
                _append ('[companies] failed to obtain browser manager')
                logging .getLogger ('dv_admin_automator.ui.web.api.routes_companies').error ('Failed to obtain browser manager for session %s',session )
                return False 
            driver =mgr .driver 
            try :
                from selenium .webdriver .common .by import By 
                from selenium .webdriver .support .ui import WebDriverWait 
                from selenium .webdriver .support import expected_conditions as EC 
            except Exception as e :
                _append (f'[companies] selenium imports failed: {e }')
                return False 
                _append ('[companies] navigating to moodashboard and logging in')
                logging .getLogger ('dv_admin_automator.ui.web.api.routes_companies').info ('Navigating to moodashboard to login (job %s)',public_job_id )
            driver .get ('https://webapp.moodar.com.br/moodashboard/')
            time .sleep (1 )
            wait =WebDriverWait (driver ,15 )
            try :
                u_field =wait .until (EC .presence_of_element_located ((By .CSS_SELECTOR ,"input[type='text'], input[name='username'], input[name='user'], input[id*='username'], input[id*='user'], input[placeholder*='usuário'], input[placeholder*='username']")))
                p_field =driver .find_element (By .CSS_SELECTOR ,"input[type='password'], input[name='password'], input[id*='password'], input[placeholder*='senha']")
                u_field .clear ();u_field .send_keys (username )
                p_field .clear ();p_field .send_keys (password )
                try :
                    login_btn =driver .find_element (By .CSS_SELECTOR ,"button[type='submit'], input[type='submit'], button[class*='login'], button[class*='entrar']")
                    login_btn .click ()
                except Exception :
                    _append ('[companies] login button not found or click failed')
                time .sleep (3 )
                _append ('[companies] login step complete')
                logging .getLogger ('dv_admin_automator.ui.web.api.routes_companies').info ('Login step complete (job %s)',public_job_id )
            except Exception as e :
                _append (f'[companies] login failed: {e }')
                return False 
            collected =[]
            seen_ids =set ()
            p =0 
            max_pages =500 
            while p <max_pages :
                url =f'https://webapp.moodar.com.br/moodashboard/corporate/company/?p={p }'
                _append (f'[companies] visiting {url }')
                try :
                    driver .get (url )
                    time .sleep (1.2 )
                except Exception as e :
                    _append (f'[companies] navigation error: {e }')
                    break 
                try :
                    rows =driver .find_elements (By .CSS_SELECTOR ,'table tbody tr')
                except Exception :
                    rows =[]
                if not rows :
                    _append (f'[companies] no rows found on page {p } — stopping')
                    break 
                new_on_page =0 
                for tr in rows :
                    try :
                        cid =None 
                        name =''
                        try :
                            tds =tr .find_elements (By .TAG_NAME ,'td')
                            if tds and len (tds )>=2 :
                                try :
                                    a =tds [0 ].find_element (By .CSS_SELECTOR ,'a')
                                    href =(a .get_attribute ('href')or '')
                                    import re 
                                    m =re .search (r'/company/([0-9A-Za-z_-]+)',href )
                                    cid =m .group (1 )if m else None 
                                except Exception :
                                    try :
                                        a =tr .find_element (By .CSS_SELECTOR ,'a')
                                        href =(a .get_attribute ('href')or '')
                                        import re 
                                        m =re .search (r'/company/([0-9A-Za-z_-]+)',href )
                                        cid =m .group (1 )if m else None 
                                    except Exception :
                                        cid =None 
                                try :
                                    name =tds [1 ].text .strip ()
                                except Exception :
                                    name =''
                            else :
                                try :
                                    a =tr .find_element (By .CSS_SELECTOR ,'a')
                                    href =a .get_attribute ('href')or ''
                                    import re 
                                    m =re .search (r'/company/([0-9A-Za-z_-]+)',href )
                                    cid =m .group (1 )if m else None 
                                    name =a .text .strip ()or ''
                                except Exception :
                                    try :
                                        tds =tr .find_elements (By .TAG_NAME ,'td')
                                        if tds :
                                            name =tds [0 ].text .strip ()
                                    except Exception :
                                        name =''
                        except Exception :
                            try :
                                a =tr .find_element (By .CSS_SELECTOR ,'a')
                                href =a .get_attribute ('href')or ''
                                import re 
                                m =re .search (r'/company/([0-9A-Za-z_-]+)',href )
                                cid =m .group (1 )if m else None 
                                name =a .text .strip ()or ''
                            except Exception :
                                continue 
                        if cid and cid not in seen_ids :
                            seen_ids .add (cid )
                            collected .append ({'id':str (cid ),'name':name })
                            new_on_page +=1 
                    except Exception :
                        continue 
                _append (f'[companies] page {p } collected {new_on_page } new companies (total {len (collected )})')
                logging .getLogger ('dv_admin_automator.ui.web.api.routes_companies').info ('Page %s collected %s new companies (total %s)',p ,new_on_page ,len (collected ))
                if new_on_page ==0 :
                    _append ('[companies] no new companies on this page, stopping pagination')
                    break 
                p +=1 
            try :
                now =datetime .datetime .now ()
                fname =f"companies_cache_{now .strftime ('%Y%m%d_%H')}.json"
                path =os .path .join (os .getcwd (),fname )
                with open (path ,'w',encoding ='utf-8')as fh :
                    json .dump (collected ,fh ,ensure_ascii =False ,indent =2 )
                _append (f'[companies] saved {len (collected )} companies to {path }')
                logging .getLogger ('dv_admin_automator.ui.web.api.routes_companies').info ('Saved %s companies to %s',len (collected ),path )
                try :
                    secure_dir =None 
                    try :
                        from dv_admin_automator .activation .storage import LocalStore 
                        store =LocalStore ()
                        store .ensure_dirs ()
                        secure_dir =str (store .creds_dir )
                    except Exception :
                        try :
                            from moodar .config import cfg 
                            secure_dir =cfg .get_secure_dir ()
                        except Exception :
                            secure_dir =os .environ .get ('MOODAR_SECURE_DIR')
                    if secure_dir :
                        try :
                            os .makedirs (secure_dir ,exist_ok =True )
                        except Exception :
                            pass 
                        legacy_path =os .path .join (secure_dir ,'companies_cache.json')
                        try :
                            legacy_map ={str (item .get ('id')):item .get ('name','')for item in collected }
                        except Exception :
                            legacy_map ={}
                        if legacy_map :
                            temp_fd ,temp_path =tempfile .mkstemp (dir =secure_dir ,prefix ='companies_cache_',suffix ='.tmp')
                            try :
                                with os .fdopen (temp_fd ,'w',encoding ='utf-8')as tf :
                                    json .dump (legacy_map ,tf ,ensure_ascii =False ,indent =2 )
                                os .replace (temp_path ,legacy_path )
                                _append (f'[companies] wrote legacy cache to {legacy_path }')
                                logging .getLogger ('dv_admin_automator.ui.web.api.routes_companies').info ('Wrote legacy companies cache to %s',legacy_path )
                            except Exception as e :
                                _append (f'[companies] failed to write legacy cache: {e }')
                                try :
                                    os .remove (temp_path )
                                except Exception :
                                    pass 
                except Exception :
                    pass 
            except Exception as e :
                _append (f'[companies] failed to save cache: {e }')
                return False 
            return True 
        except Exception as e :
            _append (f'[companies] exception: {e }')
            return False 
        finally :
            try :
                if 'session'in locals ()and session :
                    try :
                        pool .close_session (session )
                        _append (f'[companies] browser session {session } closed')
                    except Exception :
                        _append (f'[companies] failed to close browser session {session }')
            except Exception :
                pass 
    internal =get_default_manager ().submit (_job )
    _PUBLIC_TO_INTERNAL [public_job_id ]=internal 
    _COMPANY_JOB_LOGS .setdefault (public_job_id ,[]).append (f'submitted internal job {internal }')
    return JSONResponse ({'ok':True ,'job_id':public_job_id })
@router .get ('/api/companies/legacy')
async def api_companies_legacy ():
    try :
        from dv_admin_automator .activation .storage import LocalStore 
        store =LocalStore ()
        creds_dir =store .creds_dir 
        legacy_path =creds_dir /'companies_cache.json'
        if legacy_path .exists ():
            try :
                data =json .loads (legacy_path .read_text (encoding ='utf-8'))
                if isinstance (data ,dict ):
                    return JSONResponse (data )
            except Exception :
                return JSONResponse ({})
    except Exception :
        return JSONResponse ({})
    return JSONResponse ({})
@router .get ('/api/companies/{job_id}/logs')
async def api_companies_logs (job_id :str ):
    logs =_COMPANY_JOB_LOGS .get (job_id ,[])
    return JSONResponse ({'ok':True ,'logs':logs })
@router .get ('/api/companies/{job_id}/status')
async def api_companies_status (job_id :str ):
    internal =_PUBLIC_TO_INTERNAL .get (job_id )
    jm =get_default_manager ()
    lookup =internal or job_id 
    st =jm .status (lookup )
    if st is None :
        raise HTTPException (status_code =404 ,detail ='job not found')
    return JSONResponse ({'ok':True ,'status':st })