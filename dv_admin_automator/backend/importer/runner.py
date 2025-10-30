import os 
import time 
import traceback 
from typing import Callable ,Optional ,Tuple 
from ...browser .pool import get_default_pool 
LOG_PREFIX ='[import_runner]'
def _safe_log (log_fn :Callable [[str ,str ],None ],job_id :str ,msg :str ):
    try :
        log_fn (job_id ,f"{LOG_PREFIX } {msg }")
    except Exception :
        pass 
def run_import (upload_path :str ,job_id :str ,log_fn :Callable [[str ,str ],None ],*,
browser_session_id :Optional [str ]=None ,
headless :bool =True ,minimized :bool =False ,
company_name :str ='',import_type :str ='auto',
auto_confirm :bool =True )->Tuple [bool ,bool ,Optional [str ]]:
    pool =get_default_pool ()
    manager =None 
    created_local =False 
    try :
        _safe_log (log_fn ,job_id ,'starting import')
        if browser_session_id :
            manager =pool .get_manager (browser_session_id )
            if manager :
                _safe_log (log_fn ,job_id ,f'reusing browser session {browser_session_id }')
            else :
                _safe_log (log_fn ,job_id ,f'no session {browser_session_id } found; will create new browser')
        if not manager :
            _safe_log (log_fn ,job_id ,f'creating temporary browser (headless={headless })')
            session =pool .create_session (headless =headless )
            manager =pool .get_manager (session )
            created_local =True 
        if getattr (manager ,'driver',None ):
            driver =manager .driver 
        else :
            driver =manager .start ()if hasattr (manager ,'start')else None 
        try :
            from selenium .webdriver .common .by import By 
            from selenium .webdriver .support .ui import WebDriverWait 
            from selenium .webdriver .support import expected_conditions as EC 
            from selenium .webdriver .support .ui import Select 
        except Exception as e :
            _safe_log (log_fn ,job_id ,f'selenium imports failed: {e }')
            return False 
        urls ={
        'import_cpf':'https://webapp.moodar.com.br/moodashboard/corporate/basecpfemployeescompanies/import/',
        'import_email':'https://webapp.moodar.com.br/moodashboard/corporate/baseemailsemployeescompanies/import/'
        }
        target_urls =[]
        if import_type =='cpf':
            target_urls =[urls ['import_cpf']]
        elif import_type =='email':
            target_urls =[urls ['import_email']]
        else :
            target_urls =[urls ['import_cpf'],urls ['import_email']]
        success =False 
        for url in target_urls :
            try :
                _safe_log (log_fn ,job_id ,f'navigating to {url }')
                manager .driver .get (url )
                time .sleep (1 )
                file_input =None 
                try :
                    file_input =manager .driver .find_element (By .NAME ,'import_file')
                except Exception :
                    pass 
                if not file_input :
                    try :
                        file_input =manager .driver .find_element (By .CSS_SELECTOR ,"input[type='file']")
                    except Exception :
                        pass 
                if not file_input :
                    try :
                        candidates =manager .driver .find_elements (By .XPATH ,"//input[contains(@id,'file') or contains(@name,'file') or contains(@id,'import') or contains(@name,'import')]")
                        if candidates and len (candidates )>0 :
                            file_input =candidates [0 ]
                    except Exception :
                        pass 
                if not file_input :
                    _safe_log (log_fn ,job_id ,f'file input not found at {url }');
                    continue 
                abs_path =os .path .abspath (upload_path )
                _safe_log (log_fn ,job_id ,f'selecting file {abs_path }')
                file_input .send_keys (abs_path )
                try :
                    sel =Select (manager .driver .find_element (By .NAME ,'input_format'))
                    sel .select_by_value ('0')
                except Exception :
                    _safe_log (log_fn ,job_id ,'format select not found - continuing')
                try :
                    submit_btn =manager .driver .find_element (By .CSS_SELECTOR ,"input[type='submit'], button[type='submit']")
                    submit_btn .click ()
                except Exception :
                    _safe_log (log_fn ,job_id ,'submit button not found or click failed')
                time .sleep (2 )
                _safe_log (log_fn ,job_id ,'upload step completed; waiting for preview/confirm')
                try :
                    confirm_btn =None 
                    try :
                        confirm_btn =manager .driver .find_element (By .CSS_SELECTOR ,"button[name='confirm'], input[type='submit'][value*='Confirm']")
                    except Exception :
                        try :
                            confirm_btn =manager .driver .find_element (By .XPATH ,"//button[contains(., 'Confirm') or contains(., 'Confirmar')]")
                        except Exception :
                            confirm_btn =None 
                        if confirm_btn :
                            if auto_confirm :
                                _safe_log (log_fn ,job_id ,'clicking confirm')
                                confirm_btn .click ()
                                time .sleep (1 )
                                _safe_log (log_fn ,job_id ,'confirm clicked')
                            else :
                                _safe_log (log_fn ,job_id ,'awaiting manual confirmation by user (auto_confirm disabled)')
                                sid =None 
                                try :
                                    sid =getattr (manager ,'session_id',None )
                                except Exception :
                                    sid =None 
                                return True ,True ,sid 
                except Exception :
                    _safe_log (log_fn ,job_id ,'confirm step failed (non-fatal)')
                try :
                    try :
                        page_src =manager .driver .page_source or ''
                    except Exception :
                        page_src =''
                    if page_src and ('confirmar'in page_src .lower ()or 'confirm'in page_src .lower ()):
                        _safe_log (log_fn ,job_id ,'detected confirm-like text in page; awaiting manual confirmation (heuristic)')
                        sid =None 
                        try :
                            sid =getattr (manager ,'session_id',None )
                        except Exception :
                            sid =None 
                        return True ,True ,sid 
                except Exception :
                    pass 
                success =True 
                break 
            except Exception as e :
                _safe_log (log_fn ,job_id ,f'exception while processing {url }: {e }\n{traceback .format_exc ()}')
        if success :
            _safe_log (log_fn ,job_id ,'import run completed')
            return True ,False ,(getattr (manager ,'session_id',None )if manager else None )
        else :
            _safe_log (log_fn ,job_id ,'import run failed for all candidate urls')
            return False ,False ,None 
    except Exception as e :
        _safe_log (log_fn ,job_id ,f'exception: {e }\n{traceback .format_exc ()}')
        return False ,False ,None 
    finally :
        if created_local :
            try :
                pool =get_default_pool ()
                now =time .time ()
                to_close =[]
                for sid ,info in list (pool ._sessions .items ()):
                    if now -info .get ('created_at',0 )<15 :
                        to_close .append (sid )
                for sid in to_close :
                    try :
                        pool .close_session (sid )
                    except Exception :
                        pass 
            except Exception :
                pass 
def confirm_import_session (session_id :str ,job_id :str ,log_fn :Callable [[str ,str ],None ])->bool :
    try :
        pool =get_default_pool ()
        manager =pool .get_manager (session_id )
        if not manager or not getattr (manager ,'driver',None ):
            _safe_log (log_fn ,job_id ,f'confirm_import_session: no active manager for session {session_id }')
            return False 
        driver =manager .driver 
        try :
            from selenium .webdriver .common .by import By 
        except Exception as e :
            _safe_log (log_fn ,job_id ,f'confirm_import_session: selenium import failed: {e }')
            return False 
        try :
            confirm_btn =None 
            try :
                confirm_btn =driver .find_element (By .CSS_SELECTOR ,"button[name='confirm'], input[type='submit'][value*='Confirm']")
            except Exception :
                try :
                    confirm_btn =driver .find_element (By .XPATH ,"//button[contains(., 'Confirm') or contains(., 'Confirmar')]")
                except Exception :
                    confirm_btn =None 
            if not confirm_btn :
                _safe_log (log_fn ,job_id ,'confirm_import_session: confirm button not found')
                return False 
            _safe_log (log_fn ,job_id ,'confirm_import_session: clicking confirm')
            confirm_btn .click ()
            time .sleep (1 )
            _safe_log (log_fn ,job_id ,'confirm_import_session: clicked')
            return True 
        except Exception as e :
            _safe_log (log_fn ,job_id ,f'confirm_import_session exception: {e }')
            return False 
    except Exception as e :
        try :
            _safe_log (log_fn ,job_id ,f'confirm_import_session outer exception: {e }')
        except Exception :
            pass 
        return False 