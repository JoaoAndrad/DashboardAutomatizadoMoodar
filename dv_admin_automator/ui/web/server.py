import asyncio 
import socket 
import secrets 
import threading 
import json 
import webbrowser 
import os 
from pathlib import Path 
from typing import Optional 
try :
    from dotenv import load_dotenv 
    _project_root =Path (__file__ ).resolve ().parents [3 ]
    _env_path =_project_root /'.env'
    if _env_path .exists ():
        load_dotenv (dotenv_path =str (_env_path ))
    else :
        try :
            load_dotenv ()
        except Exception :
            pass 
except Exception :
    pass 
from fastapi import FastAPI ,HTTPException ,Request ,WebSocket 
from fastapi .responses import FileResponse ,JSONResponse 
from fastapi .staticfiles import StaticFiles 
import requests 
import threading 
import time 
import logging 
from ...activation .client import ActivationClient ,ActivationError 
import logging 
from ...activation .storage import LocalStore 
from ...activation .unlock import unlock_all 
from .api .credentials_cache import set_service_account_info 
import secrets 
app =FastAPI ()
try :
    from starlette .middleware .sessions import SessionMiddleware 
    secret =os .environ .get ('SESSION_SECRET')or secrets .token_urlsafe (32 )
    app .add_middleware (SessionMiddleware ,secret_key =secret )
except Exception as e :
    logging .getLogger ('dv_admin_automator.ui.web.server').warning (
    'SessionMiddleware not added: %s. To enable session support install "itsdangerous".',e 
    )
static_dir =Path (__file__ ).parent /"static"
if static_dir .exists ():
    @app .get ('/static/{full_path:path}',include_in_schema =False )
    async def protected_static (full_path :str ,request :Request ):
        if full_path .endswith ('.html'):
            public_pages =('welcome.html','activation.html')
            is_public =any (full_path .endswith (p )for p in public_pages )
            authenticated =False 
            try :
                authenticated =bool (request .session .get ('moodar_username'))
            except Exception :
                try :
                    authenticated =bool (request .cookies .get ('moodar_logged_in'))
                except Exception :
                    authenticated =False 
            if not authenticated and not is_public :
                welcome =static_dir /'welcome.html'
                if welcome .exists ():
                    return FileResponse (str (welcome ),media_type ='text/html')
        candidate =static_dir /full_path 
        if candidate .exists ()and candidate .is_file ():
            return FileResponse (str (candidate ))
        raise HTTPException (status_code =404 ,detail ='not found')
    app .mount ("/static",StaticFiles (directory =str (static_dir ),html =True ),name ="static")
    @app .get ("/",include_in_schema =False )
    async def index ():
        welcome =static_dir /"welcome.html"
        if welcome .exists ():
            return FileResponse (str (welcome ),media_type ="text/html")
        idx =static_dir /"index.html"
        if idx .exists ():
            return FileResponse (str (idx ),media_type ="text/html")
        raise HTTPException (status_code =404 ,detail ="not found")
@app .post ("/api/activate")
async def api_activate (payload :dict ,request :Request ):
    code =payload .get ("code")
    mpw =payload .get ("master_password")
    base_url =request .headers .get ("x-activation-base-url")or payload .get ("base_url")or os .environ .get ("ACTIVATION_BASE_URL","https://moodar-activation.squareweb.app")
    if not code or not mpw :
        raise HTTPException (status_code =400 ,detail ="code and master_password required")
    client =ActivationClient (base_url )
    try :
        client .confirm_code (code )
        envelope =client .submit_master_key (code ,mpw )
        store =LocalStore ()
        store .ensure_dirs ()
        saved =[]
        errors =[]
        for c in envelope .get ("credentials",[]):
            name =c .get ("name")
            token =c .get ("token")
            salt =c .get ("salt")
            try :
                p =store .save_credential (name ,token ,salt )
                from ...activation .verify import verify_token 
                verify_token (token ,salt ,mpw )
                saved .append (str (p .resolve ()))
            except Exception as ex :
                errors .append ({"name":name ,"error":str (ex )})
        if saved :
            store .save_state ({"activated":True })
        return JSONResponse ({"ok":True ,"saved":saved ,"errors":errors })
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =str (e ))
@app .post ('/api/confirm_code')
async def api_confirm_code (payload :dict ,request :Request ):
    code =payload .get ('code')
    base_url =request .headers .get ('x-activation-base-url')or payload .get ('base_url')or os .environ .get ('ACTIVATION_BASE_URL','https://moodar-activation.squareweb.app')
    if not code :
        raise HTTPException (status_code =400 ,detail ='code required')
    client =ActivationClient (base_url )
    try :
        client .confirm_code (code )
        return JSONResponse ({'ok':True ,'message':'code valid'})
    except ActivationError as e :
        raise HTTPException (status_code =400 ,detail =str (e ))
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =str (e ))
@app .post ('/api/request_activation')
async def api_request_activation (payload :dict ,request :Request ):
    base_url =request .headers .get ('x-activation-base-url')or payload .get ('base_url')or os .environ .get ('ACTIVATION_BASE_URL','https://moodar-activation.squareweb.app')
    client =ActivationClient (base_url )
    logger =logging .getLogger ('dv_admin_automator.ui.web.server')
    logger .info ('request_activation received payload: %s',payload )
    try :
        forward ={}
        if 'device_info'in payload :
            forward ['device_info']=payload .get ('device_info')
        if 'contact'in payload :
            forward ['contact']=payload .get ('contact')
        if 'metadata'in payload :
            forward ['metadata']=payload .get ('metadata')
        url =f"{client .base_url }/request_activation"
        logger .info ('forwarding to %s with payload: %s',url ,forward )
        resp =requests .post (url ,json =forward ,timeout =client .timeout )
        if resp .status_code !=200 and resp .status_code !=201 :
            try :
                j =resp .json ()
                raise HTTPException (status_code =resp .status_code ,detail =str (j ))
            except Exception :
                raise HTTPException (status_code =resp .status_code ,detail =resp .text )
        try :
            return JSONResponse ({'ok':True ,'response':resp .json ()})
        except Exception :
            return JSONResponse ({'ok':True ,'text':resp .text })
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =str (e ))
@app .get ('/api/request_status/{request_id}')
async def api_request_status (request_id :int ,request :Request ):
    base_url =request .headers .get ('x-activation-base-url')or os .environ .get ('ACTIVATION_BASE_URL','https://moodar-activation.squareweb.app')
    client =ActivationClient (base_url )
    try :
        url =f"{client .base_url }/request_status/{request_id }"
        resp =requests .get (url ,timeout =client .timeout )
        resp .raise_for_status ()
        return JSONResponse ({'ok':True ,'response':resp .json ()})
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =str (e ))
@app .post ("/api/unlock")
async def api_unlock (payload :dict ,request :Request ):
    mpw =payload .get ("master_password")
    if not mpw :
        raise HTTPException (status_code =400 ,detail ="master_password required")
    store =LocalStore ()
    try :
        creds =unlock_all (store ,mpw )
        sa_info =None 
        for name ,data in creds .items ():
            try :
                if isinstance (data ,(bytes ,bytearray )):
                    text =data .decode ('utf-8')
                else :
                    text =str (data )
                parsed =None 
                try :
                    parsed =json .loads (text )
                except Exception :
                    parsed =None 
                if isinstance (parsed ,dict )and (parsed .get ('type')=='service_account'or ('client_email'in parsed and 'private_key'in parsed )):
                    sa_info =parsed 
                    break 
            except Exception :
                continue 
        if sa_info is not None :
            try :
                set_service_account_info (sa_info ,ttl =15 *60 )
            except Exception :
                pass 
        summary ={k :len (v )for k ,v in creds .items ()}
        return JSONResponse ({"ok":True ,"credentials":summary ,"cached_service_account":bool (sa_info )})
    except Exception as e :
        raise HTTPException (status_code =403 ,detail =str (e ))
@app .get ("/api/credentials")
async def api_credentials (request :Request ):
    store =LocalStore ()
    if not store .creds_dir .exists ():
        return JSONResponse ({"credentials":[]})
    items =[]
    for p in sorted (store .creds_dir .iterdir ()):
        if p .suffix =='.enc':
            items .append ({"name":p .name })
    return JSONResponse ({"credentials":items })
@app .get ("/api/credentials/{name}/download")
async def api_credential_download (name :str ,request :Request ):
    store =LocalStore ()
    p =store .creds_dir /name 
    if not p .exists ():
        raise HTTPException (status_code =404 ,detail ="not found")
    return FileResponse (str (p ),media_type ='text/plain',filename =name )
@app .websocket ("/ws/logs/{run_id}")
async def websocket_logs (websocket :WebSocket ,run_id :str ):
    await websocket .accept ()
    try :
        for i in range (20 ):
            await websocket .send_text (f"run {run_id } - log: step {i }")
            await asyncio .sleep (0.3 )
    finally :
        await websocket .close ()
RUNS ={}
@app .post ('/api/run')
async def api_run (payload :dict ):
    run_id =secrets .token_urlsafe (8 )
    RUNS [run_id ]={'status':'running'}
    return JSONResponse ({'run_id':run_id })
def _find_free_port ():
    s =socket .socket (socket .AF_INET ,socket .SOCK_STREAM )
    s .bind (("127.0.0.1",0 ))
    addr ,port =s .getsockname ()
    s .close ()
    return port 
def serve_in_thread (open_browser :bool =True ):
    import uvicorn 
    port =_find_free_port ()
    url =f"http://127.0.0.1:{port }/"
    def run ():
        uvicorn .run (app ,host ="127.0.0.1",port =port ,log_level ="info")
    thread =threading .Thread (target =run ,daemon =False )
    thread .start ()
    import time ,socket as _socket 
    start =time .time ()
    timeout =5.0 
    while time .time ()-start <timeout :
        try :
            s =_socket .socket (_socket .AF_INET ,_socket .SOCK_STREAM )
            s .settimeout (0.2 )
            s .connect (("127.0.0.1",port ))
            s .close ()
            break 
        except Exception :
            time .sleep (0.05 )
    if open_browser :
        webbrowser .open (url )
    return url ,thread 
@app .get ('/tmp_uploads/{file_name:path}',include_in_schema =False )
async def serve_tmp_upload (file_name :str ):
    base =Path (os .getcwd ())/'tmp_uploads'
    target =(base /file_name ).resolve ()
    try :
        if not str (target ).startswith (str (base .resolve ())):
            raise HTTPException (status_code =403 ,detail ='forbidden')
        if not target .exists ()or not target .is_file ():
            raise HTTPException (status_code =404 ,detail ='not found')
        return FileResponse (str (target ))
    except HTTPException :
        raise 
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =str (e ))
if __name__ =='__main__':
    serve_in_thread (True )
try :
    from .api .routes_auth import router as auth_router 
    app .include_router (auth_router ,prefix ="/api")
except Exception :
    logging .getLogger ('dv_admin_automator.ui.web.server').info ('auth router not available during import')
try :
    from .api .routes_import import router as import_router 
    app .include_router (import_router )
except Exception :
    logging .getLogger ('dv_admin_automator.ui.web.server').info ('import routes not available during import')
try :
    from .api .routes_keepalive import router as keepalive_router 
    app .include_router (keepalive_router ,prefix ="/api")
except Exception :
    logging .getLogger ('dv_admin_automator.ui.web.server').info ('keepalive router not available during import')
try :
    from .api .routes_companies import router as companies_router 
    app .include_router (companies_router )
except Exception :
    logging .getLogger ('dv_admin_automator.ui.web.server').info ('companies router not available during import')
try :
    from .api .routes_appointments import router as appointments_router 
    app .include_router (appointments_router )
except Exception :
    logging .getLogger ('dv_admin_automator.ui.web.server').info ('appointments router not available during import')
try :
    from .api .routes_acolhimentos import router as acolhimentos_router 
    app .include_router (acolhimentos_router )
except Exception :
    logging .getLogger ('dv_admin_automator.ui.web.server').info ('acolhimentos router not available during import')
try :
    from .api .routes_reports import router as reports_router 
    app .include_router (reports_router )
except Exception :
    logging .getLogger ('dv_admin_automator.ui.web.server').info ('reports router not available during import')