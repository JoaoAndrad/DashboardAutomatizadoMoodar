import os 
import time 
import re 
import tempfile 
import traceback 
from typing import Callable ,Optional ,Dict ,Any 

import pandas as pd 

from ...browser .pool import get_default_pool 

LOG_PREFIX ='[legacy_adapter]'


def _safe_log (log_fn :Callable [[str ,str ],None ],job_id :str ,msg :str ):
    try :
        log_fn (job_id ,f"{LOG_PREFIX } {msg }")
    except Exception :
        pass 


def read_file_smart (path :str ,log_fn :Callable [[str ,str ],None ],job_id :str )->Optional [pd .DataFrame ]:
    _safe_log (log_fn ,job_id ,f"reading file {os .path .basename (path )}")
    ext =os .path .splitext (path )[1 ].lower ()
    try :
        if ext =='.csv'or ext =='.txt':
            encodings =['utf-8','utf-8-sig','latin-1']
            for enc in encodings :
                try :
                    df =pd .read_csv (path ,encoding =enc )
                    _safe_log (log_fn ,job_id ,f'read CSV with encoding={enc } (rows={len (df )})')
                    return df 
                except Exception as e :
                    _safe_log (log_fn ,job_id ,f'failed read with {enc }: {e }')
            return None 
        elif ext in ('.xlsx','.xls'):
            df =pd .read_excel (path ,engine ='openpyxl')
            _safe_log (log_fn ,job_id ,f'read excel (rows={len (df )})')
            return df 
        else :
            _safe_log (log_fn ,job_id ,'unsupported file extension')
            return None 
    except Exception as e :
        _safe_log (log_fn ,job_id ,f'read_file_smart exception: {e }\n{traceback .format_exc ()}')
        return None 


def detect_columns_by_content (df :pd .DataFrame )->Dict [str ,Optional [str ]]:
    def looks_like_cpf (s :str )->bool :
        s =re .sub (r'\D','',str (s ))
        return len (s )==11 

    def looks_like_email (s :str )->bool :
        s =str (s )
        return '@'in s and '.'in s 

    result :Dict [str ,Optional [str ]]={'cpf':None ,'email':None ,'name':None }
    for col in df .columns :
        sample =df [col ].dropna ().astype (str ).head (20 )
        if len (sample )==0 :
            continue 
        cpf_count =sum (1 for v in sample if looks_like_cpf (v ))
        email_count =sum (1 for v in sample if looks_like_email (v ))
        if cpf_count >=max (1 ,len (sample )//3 )and result ['cpf']is None :
            result ['cpf']=col 
        if email_count >=max (1 ,len (sample )//3 )and result ['email']is None :
            result ['email']=col 
        name_count =sum (1 for v in sample if isinstance (v ,str )and len (v .strip ())>2 and ' 'in v .strip ())
    if name_count >=1 and result ['name']is None :
            result ['name']=col 
    return result 


def prepare_base_cpf (df :pd .DataFrame ,cols :Dict [str ,Any ],company_id :str ,log_fn ,job_id :str )->Optional [pd .DataFrame ]:
    try :
        cpf_col =cols .get ('cpf')
        name_col =cols .get ('name')
        if not cpf_col or not name_col :
            _safe_log (log_fn ,job_id ,'prepare_base_cpf: missing columns')
            return None 
        prepared =pd .DataFrame ()
        prepared ['id']=df [cpf_col ].astype (str ).apply (lambda v :re .sub (r'\D','',v ))
        before =len (prepared )
        prepared =prepared [prepared ['id'].str .len ()==11 ]
        removed =before -len (prepared )
        if removed >0 :
            _safe_log (log_fn ,job_id ,f'prepare_base_cpf: removed {removed } rows with invalid CPF')

        def _fmt_cpf (d :str )->str :
            d =str (d )
            return f"{d [:3 ]}.{d [3 :6 ]}.{d [6 :9 ]}-{d [9 :]}"

        prepared ['id']=prepared ['id'].apply (lambda x :_fmt_cpf (x ))
        prepared ['name_employee']=df .loc [prepared .index ,name_col ].astype (str ).apply (lambda v :v .strip ())
        prepared ['company']=str (company_id )
        dedup_before =len (prepared )
        prepared =prepared .drop_duplicates (subset =['id'])
        if len (prepared )!=dedup_before :
            _safe_log (log_fn ,job_id ,f'prepare_base_cpf: dropped {dedup_before -len (prepared )} duplicate CPFs')

        prepared =prepared [['company','id','name_employee']]
        _safe_log (log_fn ,job_id ,f'prepared base cpf rows={len (prepared )}')
        return prepared 
    except Exception as e :
        _safe_log (log_fn ,job_id ,f'prepare_base_cpf exception: {e }')
        return None 


def prepare_base_email (df :pd .DataFrame ,cols :Dict [str ,Any ],company_id :str ,log_fn ,job_id :str )->Optional [pd .DataFrame ]:
    try :
        email_col =cols .get ('email')
        if not email_col :
            _safe_log (log_fn ,job_id ,'prepare_base_email: missing email column')
            return None 
        prepared =pd .DataFrame ()
        prepared ['id']=df [email_col ].astype (str ).apply (lambda v :v .strip ().lower ())
        prepared =prepared [prepared ['id'].notna ()&(prepared ['id']!='')]
        import re as _re 
        email_rx =_re .compile (r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        before =len (prepared )
        prepared =prepared [prepared ['id'].apply (lambda x :bool (email_rx .match (str (x ))))]
        after =len (prepared )
        removed =before -after 
        if removed >0 :
            _safe_log (log_fn ,job_id ,f'prepare_base_email: removed {removed } invalid email rows')
        dedup_before =len (prepared )
        prepared =prepared .drop_duplicates (subset =['id'])
        dedup_after =len (prepared )
        if dedup_after !=dedup_before :
            _safe_log (log_fn ,job_id ,f'prepare_base_email: dropped {dedup_before -dedup_after } duplicate emails')
        prepared ['company']=str (company_id )
        prepared =prepared [['company','id']]
        _safe_log (log_fn ,job_id ,f'prepared base email rows={len (prepared )}')
        return prepared 
    except Exception as e :
        _safe_log (log_fn ,job_id ,f'prepare_base_email exception: {e }')
        return None 


def write_csv_with_fallback (df :pd .DataFrame ,target_path :str ,log_fn ,job_id :str )->Optional [str ]:
    encodings =['utf-8','utf-8-sig','latin-1']
    try :
        df =df .copy ()
        df .columns =[str (c ).lstrip ('\ufeff').strip ()for c in df .columns ]
    except Exception :
        pass 
    for enc in encodings :
        try :
            dirn =os .path .dirname (target_path )or '.'
            fd ,tmp =tempfile .mkstemp (prefix ='upload_',dir =dirn ,text =False )
            os .close (fd )
            df .to_csv (tmp ,encoding =enc ,index =False )
            os .replace (tmp ,target_path )
            _safe_log (log_fn ,job_id ,f'wrote CSV {target_path } with encoding={enc }')
            return enc 
        except Exception as e :
            _safe_log (log_fn ,job_id ,f'write with {enc } failed: {e }')
            try :
                if os .path .exists (tmp ):
                    os .remove (tmp )
            except Exception :
                pass 
    return None 


def fetch_companies_map_via_admin (pool ,session_id :Optional [str ],log_fn ,job_id :str )->Dict [str ,str ]:
    out ={}
    manager =None 
    try :
        if session_id :
            manager =pool .get_manager (session_id )
        if not manager :
            sid =pool .create_session (headless =False )
            manager =pool .get_manager (sid )

        driver =manager .start ()if not getattr (manager ,'driver',None )else manager .driver 
        base ='https://webapp.moodar.com.br/moodashboard/corporate/company/?p='
        page =0 
        while True :
            url =base +str (page )
            _safe_log (log_fn ,job_id ,f'visiting {url }')
            driver .get (url )
            time .sleep (1 )
            rows =driver .find_elements ('css selector','table#result_list tbody tr')
            if not rows :
                break 
            newly =0 
            for tr in rows :
                try :
                    link =None 
                    try :
                        link =tr .find_element ('css selector','th a')
                        href =link .get_attribute ('href')or ''
                        m =re .search (r'/company/(\d+)/',href )
                        cid =m .group (1 )if m else (link .text or '').strip ()
                    except Exception :
                        cid =''
                    name =''
                    try :
                        cols =tr .find_elements ('css selector','td')
                        if len (cols )>=1 :
                            name =cols [0 ].text .strip ()
                    except Exception :
                        name =''
                    if cid and name and cid not in out :
                        out [str (cid )]=name 
                        newly +=1 
                except Exception :
                    pass 
            _safe_log (log_fn ,job_id ,f'page {page } collected {newly } new companies (total {len (out )})')
            if newly ==0 :
                break 
            page +=1 
        return out 
    except Exception as e :
        _safe_log (log_fn ,job_id ,f'fetch_companies_map exception: {e }\n{traceback .format_exc ()}')
        return out 


def run_import_full (upload_path :str ,job_id :str ,log_fn :Callable [[str ,str ],None ],*,
browser_session_id :Optional [str ]=None ,
headless :bool =True ,minimized :bool =False ,
company_name :Optional [str ]=None ,company_id :Optional [str ]=None ,
import_type :str ='auto')->bool :

    pool =get_default_pool ()
    try :
        _safe_log (log_fn ,job_id ,f'starting full import for {os .path .basename (upload_path )}')

        df =read_file_smart (upload_path ,log_fn ,job_id )
        if df is None :
            _safe_log (log_fn ,job_id ,'could not read input file')
            return False 

        cols =detect_columns_by_content (df )
        _safe_log (log_fn ,job_id ,f'detected columns {cols }')

        resolved_company_id =company_id 
        if not resolved_company_id :
            if company_name :
                try :
                    from dv_admin_automator .activation .storage import LocalStore 
                    import json 
                    store =LocalStore ()
                    legacy_path =os .path .join (store .creds_dir ,'companies_cache.json')
                    if os .path .exists (legacy_path ):
                        _safe_log (log_fn ,job_id ,f'loading legacy companies cache from {legacy_path }')
                        try :
                            with open (legacy_path ,'r',encoding ='utf-8')as fh :
                                legacy_map =json .load (fh )
                            for cid ,nm in legacy_map .items ():
                                if isinstance (nm ,str )and nm .strip ().lower ()==company_name .strip ().lower ():
                                    resolved_company_id =cid 
                                    break 
                            if not resolved_company_id :
                                for cid ,nm in legacy_map .items ():
                                    if isinstance (nm ,str )and company_name .strip ().lower ()in nm .strip ().lower ():
                                        resolved_company_id =cid 
                                        break 
                        except Exception as e :
                            _safe_log (log_fn ,job_id ,f'failed to read legacy cache: {e }')
                except Exception :
                    pass 

                if not resolved_company_id :
                    mapping =fetch_companies_map_via_admin (pool ,browser_session_id ,log_fn ,job_id )
                    for cid ,nm in mapping .items ():
                        if nm .strip ().lower ()==company_name .strip ().lower ():
                            resolved_company_id =cid 
                            break 
                    if not resolved_company_id :
                        for cid ,nm in mapping .items ():
                            if company_name .strip ().lower ()in nm .strip ().lower ():
                                resolved_company_id =cid 
                                break 
        if not resolved_company_id :
            _safe_log (log_fn ,job_id ,'company id not provided and could not be resolved')
            return False 

        final_df =None 
        the_type =import_type 
        if the_type =='auto':
            the_type ='cpf'if cols .get ('cpf')and cols .get ('name')else ('email'if cols .get ('email')else 'email')

        if the_type =='cpf':
            final_df =prepare_base_cpf (df ,cols ,resolved_company_id ,log_fn ,job_id )
        else :
            final_df =prepare_base_email (df ,cols ,resolved_company_id ,log_fn ,job_id )

        if final_df is None or len (final_df )==0 :
            _safe_log (log_fn ,job_id ,'no rows prepared for import')
            return False 

        tmp_dir =os .path .join (os .getcwd (),'tmp_uploads')
        os .makedirs (tmp_dir ,exist_ok =True )
        def _sanitize (s :str )->str :
            return re .sub (r'[^A-Za-z0-9_.-]','_',s or '')
        safe_job =_sanitize (job_id )
        tmp_path =os .path .join (tmp_dir ,f'import_{safe_job }.csv')
        enc =write_csv_with_fallback (final_df ,tmp_path ,log_fn ,job_id )
        if not enc :
            _safe_log (log_fn ,job_id ,'failed to write upload CSV with any encoding')
            return False 

        try :
            from .runner import run_import 
        except Exception as e :
            _safe_log (log_fn ,job_id ,f'failed to import runner: {e }')
            return False 

        try :
            ok ,awaiting ,sid =run_import (tmp_path ,job_id ,log_fn ,browser_session_id =browser_session_id ,headless =headless ,minimized =minimized ,company_name =(company_name or ''),import_type =the_type ,auto_confirm =False )
            if awaiting :
                try :
                    marker =tmp_path +'.awaiting_confirm'
                    meta ={'tmp_path':tmp_path ,'session_id':sid }
                    import json 
                    with open (marker ,'w',encoding ='utf-8')as fh :
                        json .dump (meta ,fh )
                    _safe_log (log_fn ,job_id ,f'upload completed; awaiting manual confirmation (marker={marker })')
                    try :
                        from ...ui .web .jobs import get_default_manager ,get_current_job_id 
                        jm =get_default_manager ()
                        internal =get_current_job_id ()
                        if internal :
                            jm .set_awaiting_confirmation (internal ,True )
                            _safe_log (log_fn ,job_id ,f'set job {internal } awaiting_confirmation=True')
                    except Exception as e :
                        _safe_log (log_fn ,job_id ,f'could not set awaiting flag on JobManager: {e }')
                    try :
                        import time 
                        while os .path .exists (marker ):
                            time .sleep (1 )
                    except Exception as e :
                        _safe_log (log_fn ,job_id ,f'await loop interrupted: {e }')
                    try :
                        canceled_sentinel =marker +'.canceled'
                        if os .path .exists (canceled_sentinel ):
                            _safe_log (log_fn ,job_id ,'import canceled by operator; finalizing as canceled')
                            try :
                                os .remove (canceled_sentinel )
                            except Exception :
                                pass 
                            return False 
                        _safe_log (log_fn ,job_id ,'operator confirmed import; resuming finalization')
                        return True 
                    except Exception as e :
                        _safe_log (log_fn ,job_id ,f'error after awaiting confirmation: {e }')
                        return False 
                except Exception as e :
                    _safe_log (log_fn ,job_id ,f'failed to write awaiting_confirm marker: {e }')
                    return False 
            else :
                if ok :
                    _safe_log (log_fn ,job_id ,'full import finished successfully')
                else :
                    _safe_log (log_fn ,job_id ,'full import reported failure')
                return bool (ok )
        except Exception as e :
            _safe_log (log_fn ,job_id ,f'runner exception: {e }\n{traceback .format_exc ()}')
            return False 

    except Exception as e :
        _safe_log (log_fn ,job_id ,f'exception: {e }\n{traceback .format_exc ()}')
        return False 
