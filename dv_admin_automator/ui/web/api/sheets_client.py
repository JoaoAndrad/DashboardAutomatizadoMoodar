import os 
import json 
import logging 
from typing import List ,Dict ,Optional 
try :
    from google .oauth2 import service_account 
    from googleapiclient .discovery import build 
except Exception :
    service_account =None 
    build =None 
logger =logging .getLogger (__name__ )
try :
    from .credentials_cache import get_service_account_info 
except Exception :
    def get_service_account_info ():
        return None 
def _get_credentials (readonly :bool =True ,scopes :Optional [List [str ]]=None ):
    info =None 
    try :
        info =get_service_account_info ()
    except Exception :
        info =None 
    if info :
        if service_account is None :
            raise RuntimeError ('google-auth libraries not installed')
        if scopes :
            creds =service_account .Credentials .from_service_account_info (info ,scopes =scopes )
        else :
            scope ='https://www.googleapis.com/auth/spreadsheets.readonly'if readonly else 'https://www.googleapis.com/auth/spreadsheets'
            creds =service_account .Credentials .from_service_account_info (info ,scopes =[scope ])
        return creds 
    path =os .environ .get ('GOOGLE_SA_JSON_PATH')or os .environ .get ('GOOGLE_APPLICATION_CREDENTIALS')
    if not path :
        return None 
    if service_account is None :
        raise RuntimeError ('google-auth libraries not installed')
    if scopes :
        creds =service_account .Credentials .from_service_account_file (path ,scopes =scopes )
    else :
        scope ='https://www.googleapis.com/auth/spreadsheets.readonly'if readonly else 'https://www.googleapis.com/auth/spreadsheets'
        creds =service_account .Credentials .from_service_account_file (path ,scopes =[scope ])
    return creds 
def read_sheet_rows (sheet_id :str ,range_name :str =None )->Optional [List [Dict [str ,str ]]]:
    if not sheet_id :
        logger .warning ('read_sheet_rows called with empty sheet_id')
        return None 
    logger .info ('read_sheet_rows: attempting to read sheet_id=%s range=%s',sheet_id ,range_name or 'A:Z')
    creds =_get_credentials ()
    if creds is None :
        logger .warning ('No Google credentials available (cache/file). sheet_id=%s',sheet_id )
        return None 
    if build is None :
        logger .error ('google-api-python-client not installed - cannot call Sheets API')
        raise RuntimeError ('google-api-python-client not installed')
    service =build ('sheets','v4',credentials =creds )
    sheet =service .spreadsheets ()
    try :
        rng =range_name or 'A:Z'
        result =sheet .values ().get (spreadsheetId =sheet_id ,range =rng ).execute ()
        values =result .get ('values',[])
        if not values :
            return []
        headers =[h .strip ()for h in values [0 ]]
        rows =[]
        for row_values in values [1 :]:
            row ={}
            for i ,h in enumerate (headers ):
                row [h ]=row_values [i ]if i <len (row_values )else ''
            rows .append (row )
        return rows 
    except Exception as e :
        msg =str (e )
        if 'invalid_grant'in msg or '401'in msg or 'unauthorized'in msg .lower ()or 'authentication'in msg .lower ()or 'not authorized'in msg .lower ():
            logger .error ('Sheets API auth error for sheet_id=%s: %s',sheet_id ,msg )
        else :
            logger .exception ('Sheets API error for sheet_id=%s',sheet_id )
        return None 
def _col_index_to_letter (n :int )->str :
    letters =''
    while n >0 :
        n ,rem =divmod (n -1 ,26 )
        letters =chr (65 +rem )+letters 
    return letters 
def write_row_by_index (sheet_id :str ,row_index :int ,row_dict :Dict [str ,str ])->bool :
    logger .info ('write_row_by_index: sheet_id=%s row_index=%s',sheet_id ,row_index )
    creds =_get_credentials (readonly =False )
    if creds is None :
        logger .warning ('No credentials available for write_row_by_index sheet_id=%s',sheet_id )
        return False 
    if build is None :
        logger .error ('google-api-python-client not installed - cannot call Sheets API')
        raise RuntimeError ('google-api-python-client not installed')
    service =build ('sheets','v4',credentials =creds )
    sheet =service .spreadsheets ()
    try :
        head_res =sheet .values ().get (spreadsheetId =sheet_id ,range ='A1:1').execute ()
        headers =head_res .get ('values',[[]])[0 ]
        if not headers :
            return False 
        target_row =row_index +2 
        last_col =_col_index_to_letter (len (headers ))
        target_range =f'A{target_row }:{last_col }{target_row }'
        existing =sheet .values ().get (spreadsheetId =sheet_id ,range =target_range ).execute ().get ('values',[])
        existing_row =existing [0 ]if existing else []
        values =[]
        for i ,h in enumerate (headers ):
            key =h if h in row_dict else h .strip ()
            if key in row_dict :
                values .append (str (row_dict .get (key ,'')))
            else :
                values .append (existing_row [i ]if i <len (existing_row )else '')
        body ={'values':[values ]}
        sheet .values ().update (spreadsheetId =sheet_id ,range =target_range ,valueInputOption ='RAW',body =body ).execute ()
        return True 
    except Exception as e :
        msg =str (e )
        if 'invalid_grant'in msg or '401'in msg or 'unauthorized'in msg .lower ():
            logger .error ('Sheets API auth/write error for sheet_id=%s: %s',sheet_id ,msg )
        else :
            logger .exception ('Sheets API write error for sheet_id=%s',sheet_id )
        return False 