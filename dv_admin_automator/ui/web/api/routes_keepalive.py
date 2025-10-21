from fastapi import APIRouter ,Request 
from fastapi .responses import JSONResponse 

router =APIRouter ()


@router .get ('/keepalive')
async def api_keepalive (request :Request ):

    authenticated =False 
    try :
        authenticated =bool (request .session .get ('moodar_username'))
    except Exception :

        try :
            authenticated =bool (request .cookies .get ('moodar_logged_in'))
        except Exception :
            authenticated =False 

    if not authenticated :
        return JSONResponse ({'ok':False ,'error':'unauthenticated'},status_code =401 )
    return JSONResponse ({'ok':True })



@router .post ('/browser/keepalive')
async def api_browser_keepalive (request :Request ):

    results ={'touched':0 ,'errors':[]}
    try :

        from dv_admin_automator .browser .pool import get_default_pool 
        pool =get_default_pool ()

        try :
            payload =await request .json ()
        except Exception :
            payload ={}
        target =payload .get ('session')if isinstance (payload ,dict )else None 


        sessions =[]
        if target :
            sessions =[target ]
        else :
            try :
                sessions =list (pool ._sessions .keys ())
            except Exception :
                sessions =[]

        for sid in sessions :
            try :
                mgr =pool .get_manager (sid )
                if not mgr or not getattr (mgr ,'driver',None ):
                    continue 
                driver =mgr .driver 

                script ="try{ fetch('/', {method:'GET', credentials:'include'}).catch(function(e){}); }catch(e){};"
                try :
                    driver .execute_script (script )
                    results ['touched']+=1 
                except Exception as e :
                    results ['errors'].append ({'session':sid ,'error':str (e )})
            except Exception as e :
                results ['errors'].append ({'session':sid ,'error':str (e )})
    except Exception as e :
        return JSONResponse ({'ok':False ,'error':str (e )},status_code =500 )

    return JSONResponse ({'ok':True ,**results })


@router .get ('/browser/session/{session_id}/status')
async def api_browser_session_status (session_id :str ):

    try :
        from dv_admin_automator .browser .pool import get_default_pool 
        pool =get_default_pool ()

        exists =False 
        try :
            exists =session_id in getattr (pool ,'_sessions',{})
        except Exception :
            exists =False 

        if not exists :
            return JSONResponse ({'ok':True ,'session':session_id ,'exists':False ,'active':False ,'url':None })

        mgr =None 
        try :
            mgr =pool .get_manager (session_id )
        except Exception :
            mgr =None 

        if not mgr or not getattr (mgr ,'driver',None ):
            return JSONResponse ({'ok':True ,'session':session_id ,'exists':True ,'active':False ,'url':None })

        driver =mgr .driver 
        try :

            url =driver .execute_script ('return document.location.href;')
            return JSONResponse ({'ok':True ,'session':session_id ,'exists':True ,'active':True ,'url':url })
        except Exception as e :
            return JSONResponse ({'ok':True ,'session':session_id ,'exists':True ,'active':False ,'url':None ,'error':str (e )})
    except Exception as e :
        return JSONResponse ({'ok':False ,'error':str (e )},status_code =500 )


@router .get ('/browser/sessions')
async def api_browser_sessions ():

    try :
        from dv_admin_automator .browser .pool import get_default_pool 
        pool =get_default_pool ()
        sessions =[]
        try :
            keys =list (getattr (pool ,'_sessions',{}).keys ())
        except Exception :
            keys =[]
        for sid in keys :
            info ={'session':sid ,'exists':True ,'active':False ,'url':None ,'error':None }
            try :
                mgr =pool .get_manager (sid )
                if not mgr or not getattr (mgr ,'driver',None ):
                    sessions .append (info );continue 
                driver =mgr .driver 
                try :
                    url =driver .execute_script ('return document.location.href;')
                    info ['active']=True 
                    info ['url']=url 
                except Exception as e :
                    info ['active']=False 
                    info ['error']=str (e )
            except Exception as e :
                info ['error']=str (e )
            sessions .append (info )
        return JSONResponse ({'ok':True ,'sessions':sessions })
    except Exception as e :
        return JSONResponse ({'ok':False ,'error':str (e )},status_code =500 )
