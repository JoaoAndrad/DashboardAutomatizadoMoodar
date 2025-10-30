import os 
import csv 
import json 
import logging 
import shutil 
from datetime import datetime 
from typing import List ,Dict ,Optional ,Any 
try :
    from googleapiclient .discovery import build 
except Exception :
    build =None 
logger =logging .getLogger (__name__ )
from dv_admin_automator .ui .web .api import sheets_client 
BASE_SHEET_ID =os .environ .get (
"BASE_SHEET_ID",
os .environ .get ("BASE_SHEET_ID","1VTf5wWDp7_Tt9DRdsLhAjqgp4EAEnMdzwMCbaBqw3dM"),
)
DRIVE_FOLDER_ID =os .environ .get (
"BASE_DRIVER_FOLDER","11TK5MG_piXzNMl_hj-B3hw4z4Y2bFtJG"
)
SHEET_TAB =os .environ .get ("BASE_SHEET_TAB","Página1")
SCORE_AUTO =int (os .environ .get ("SCORE_AUTO","90"))
SCORE_REVIEW =int (os .environ .get ("SCORE_REVIEW","75"))
def normalize_name (s :str )->str :
    import unicodedata 
    if not s :
        return ""
    s =str (s )
    s =unicodedata .normalize ("NFKD",s )
    s ="".join (ch for ch in s if not unicodedata .combining (ch )).lower ()
    for tok in ["ltda","ltda.","sa","grupo",",","."]:
        s =s .replace (tok ," ")
    return " ".join (s .split ())
def fuzzy_best_match (query :str ,candidates :List [str ])->(Optional [int ],int ):
    q =normalize_name (query )
    if not q :
        return None ,0 
    try :
        from rapidfuzz import fuzz 
        score_fn =lambda a ,b :int (fuzz .token_set_ratio (a ,b ))
    except Exception :
        from difflib import SequenceMatcher 
        score_fn =lambda a ,b :int (SequenceMatcher (None ,a ,b ).ratio ()*100 )
    best_idx ,best_score =None ,-1 
    for i ,c in enumerate (candidates ):
        cand =normalize_name (c or "")
        score =score_fn (q ,cand )if cand else 0 
        if score >best_score :
            best_idx ,best_score =i ,score 
    return best_idx ,best_score 
def _get_google_service (api :str ,version :str ,readonly :bool =False ):
    scopes =None 
    if api .lower ()=='drive':
        scopes =['https://www.googleapis.com/auth/drive.readonly']if readonly else ['https://www.googleapis.com/auth/drive']
    else :
        scopes =['https://www.googleapis.com/auth/spreadsheets.readonly']if readonly else ['https://www.googleapis.com/auth/spreadsheets']
    creds =sheets_client ._get_credentials (readonly =readonly ,scopes =scopes )
    if not creds :
        logger .error ("No Google credentials available for api=%s readonly=%s",api ,readonly )
        raise RuntimeError ("No Google credentials available")
    if not build :
        logger .error ("google-api-python-client not installed (tried to build %s %s)",api ,version )
        raise RuntimeError ("google-api-python-client not installed")
    return build (api ,version ,credentials =creds )
def get_sheets_service (readonly :bool =False ):
    return _get_google_service ("sheets","v4",readonly )
def get_drive_service ():
    return _get_google_service ("drive","v3",readonly =False )
def read_master_rows (
sheet_id :str ,tab :str =SHEET_TAB ,max_rows :int =1000 
)->(List [List [Any ]],List [str ]):
    svc =get_sheets_service (readonly =True )
    rng =f"{tab }!A1:D{max_rows }"
    try :
        values =(
        svc .spreadsheets ().values ().get (spreadsheetId =sheet_id ,range =rng )
        .execute ()
        .get ("values",[])
        )
    except Exception :
        logger .exception ("Failed to read master rows from sheet_id=%s range=%s",sheet_id ,rng )
        return [],[]
    return (values [1 :],values [0 ])if values else ([],[])
def write_date_to_row (
sheet_id :str ,row_index0 :int ,date_str :str ,header :List [str ]
)->bool :
    target_col =next (
    (h for h in header if "última"in h .lower ()and "atualização"in h .lower ()),
    header [3 ]if len (header )>=4 else "Última atualização RH",
    )
    try :
        res =sheets_client .write_row_by_index (sheet_id ,row_index0 ,{target_col :date_str })
        logger .info ("Wrote date %s to sheet %s row_index0=%s column=%s",date_str ,sheet_id ,row_index0 ,target_col )
        return res 
    except Exception :
        logger .exception ("Failed to write date to row %s in sheet %s",row_index0 ,sheet_id )
        return False 
def add_sheet_tab_and_paste (spreadsheet_id :str ,tab_title :str ,csv_path :str )->bool :
    svc =get_sheets_service (False )
    tried_titles =[tab_title ]
    sanitized =None 
    try :
        import re 
        sanitized =re .sub (r"[\\\\/*?\[\]]","-",tab_title )
        if sanitized !=tab_title :
            tried_titles .append (sanitized )
    except Exception :
        sanitized =tab_title 
    successful_title =None 
    for t in tried_titles :
        try :
            svc .spreadsheets ().batchUpdate (
            spreadsheetId =spreadsheet_id ,
            body ={"requests":[{"addSheet":{"properties":{"title":t ,"index":0 }}}]},
            ).execute ()
            successful_title =t 
            break 
        except Exception :
            logger .exception ("Failed to add sheet tab %s to spreadsheet %s; trying next title if available",t ,spreadsheet_id )
    if not successful_title :
        logger .error ("Unable to add any sheet tab for titles=%s to spreadsheet %s",tried_titles ,spreadsheet_id )
        return False 
    try :
        with open (csv_path ,newline ="",encoding ="utf-8")as fh :
            values =list (csv .reader (fh ))
        svc .spreadsheets ().values ().update (
        spreadsheetId =spreadsheet_id ,
        range =f"'{successful_title }'!A1",
        valueInputOption ="RAW",
        body ={"values":values },
        ).execute ()
        logger .info ("Pasted CSV %s into spreadsheet %s tab %s",csv_path ,spreadsheet_id ,successful_title )
        return True 
    except Exception :
        logger .exception ("Failed to paste CSV %s into spreadsheet %s tab %s",csv_path ,spreadsheet_id ,successful_title )
        return False 
def create_native_sheet_and_paste (folder_id :str ,name :str ,csv_path :str )->Dict [str ,Any ]:
    drive =get_drive_service ()
    file =drive .files ().create (
    body ={"name":name ,"mimeType":"application/vnd.google-apps.spreadsheet","parents":[folder_id ]},
    fields ="id,webViewLink",
    ).execute ()
    new_id =file ["id"]
    if not add_sheet_tab_and_paste (new_id ,"data",csv_path ):
        try :
            drive .files ().delete (fileId =new_id ).execute ()
            logger .info ("Deleted newly created spreadsheet %s after failing to paste CSV",new_id )
        except Exception :
            logger .exception ("Failed to delete spreadsheet %s after paste failure",new_id )
        logger .error ("Failed to paste CSV into new sheet %s",new_id )
        raise RuntimeError ("Failed to paste CSV into new sheet")
    return {"id":new_id ,"webViewLink":file ["webViewLink"]}
def find_drive_file_by_basename (drive ,folder_id :str ,basename :str )->List [Dict [str ,Any ]]:
    safe_name =basename .replace ("'","\\'")
    query =(
    f"'{folder_id }' in parents and trashed=false "
    f"and (name='{safe_name }.csv' or name='{safe_name }.xlsx' or name contains '{safe_name }')"
    )
    files =(
    drive .files ()
    .list (q =query ,pageSize =50 ,fields ="files(id,name,mimeType,webViewLink)")
    .execute ()
    .get ("files",[])
    )
    logger .debug ("find_drive_file_by_basename query=%s found=%d files",query ,len (files ))
    exact =[f for f in files if f ["name"].rsplit (".",1 )[0 ]==basename ]
    fallback =[f for f in files if f .get ("name")==f"{basename }.xlsx"]
    return exact or fallback 
def _safe_delete (path :str )->bool :
    try :
        if path :
            if os .path .isfile (path )or os .path .islink (path ):
                os .remove (path )
                logger .info ("Removed file %s",path )
                return True 
            if os .path .isdir (path ):
                for name in os .listdir (path ):
                    full =os .path .join (path ,name )
                    try :
                        if os .path .isfile (full )or os .path .islink (full ):
                            os .remove (full )
                        else :
                            shutil .rmtree (full )
                    except Exception :
                        logger .exception ("Failed to remove %s",full )
                logger .info ("Cleared directory %s",path )
                return True 
            logger .warning ("Path not found for deletion: %s",path )
            return False 
        base =os .path .dirname (os .path .dirname (os .path .dirname (os .path .dirname (__file__ ))))
        cleaned_any =False 
        for dname in ("tmp_downloads","tmp_uploads"):
            dpath =os .path .join (base ,dname )
            if os .path .isdir (dpath ):
                for name in os .listdir (dpath ):
                    full =os .path .join (dpath ,name )
                    try :
                        if os .path .isfile (full )or os .path .islink (full ):
                            os .remove (full )
                        else :
                            shutil .rmtree (full )
                    except Exception :
                        logger .exception ("Failed to remove %s",full )
                logger .info ("Cleared temporary folder %s",dpath )
                cleaned_any =True 
            else :
                logger .debug ("Temporary folder not present, skipping: %s",dpath )
        return cleaned_any 
    except Exception :
        logger .exception ("Unexpected error in _safe_delete for path=%s",path )
        return False 
def process_company_update (company_name :str ,csv_path :Optional [str ]=None ,dry_run :bool =True )->Dict [str ,Any ]:
    rows ,header =read_master_rows (BASE_SHEET_ID )
    candidates =[r [0 ]if r else ""for r in rows ]
    idx ,score =fuzzy_best_match (company_name ,candidates )
    result ={"company":company_name ,"match_index":idx ,"score":score ,"actions":[]}
    if idx is None :
        result ["error"]="no candidates"
        return result 
    action ="create"if score <SCORE_REVIEW else "update"
    today =datetime .now ().strftime ("%d/%m/%Y")
    result .update ({"matched_value":candidates [idx ],"action":action })
    if not dry_run :
        result ["date_written"]=write_date_to_row (BASE_SHEET_ID ,idx ,today ,header )
    else :
        result ["date_written"]=False 
    cval =rows [idx ][2 ]if len (rows [idx ])>2 else ""
    drive =get_drive_service ()
    def handle_sheet (fid :str ,editable :bool ,base_name :str ):
        if editable :
            if not dry_run and csv_path :
                tab_title =datetime .now ().strftime ("%d/%m/%Y")
                success =add_sheet_tab_and_paste (fid ,tab_title ,csv_path )
                try :
                    meta =drive .files ().get (fileId =fid ,fields ="id,name,webViewLink,capabilities").execute ()
                    link =meta .get ("webViewLink")or f"https://docs.google.com/spreadsheets/d/{fid }"
                    sheets_client .write_row_by_index (
                    BASE_SHEET_ID ,
                    idx ,
                    {header [2 ]if len (header )>2 else "Base":link },
                    )
                except Exception :
                    logger .exception ("Failed to fetch/write webViewLink for editable sheet %s",fid )
                result ["actions"].append ({"type":"add_tab","target":fid ,"tab":tab_title ,"success":bool (success )})
            else :
                result ["actions"].append ({"type":"can_edit","target":fid })
        else :
            new_name =f"{base_name } - copia bot"
            if not dry_run and csv_path :
                newf =create_native_sheet_and_paste (DRIVE_FOLDER_ID ,new_name ,csv_path )
                sheets_client .write_row_by_index (
                BASE_SHEET_ID ,
                idx ,
                {header [2 ]if len (header )>2 else "Base":newf ["webViewLink"]},
                )
                result ["actions"].append ({"type":"uploaded_copy",**newf })
            else :
                result ["actions"].append ({"type":"no_edit_would_upload","target":fid })
    try :
        if "docs.google.com"in str (cval ):
            import re 
            match =re .search (r"/spreadsheets/d/([a-zA-Z0-9-_]+)",cval )
            if match :
                fid =match .group (1 )
                meta =drive .files ().get (fileId =fid ,fields ="id,name,capabilities").execute ()
                handle_sheet (fid ,meta ["capabilities"].get ("canEdit",False ),meta .get ("name","copy"))
        elif cval :
            found =find_drive_file_by_basename (drive ,DRIVE_FOLDER_ID ,str (cval ).strip ())
            if found :
                meta =drive .files ().get (fileId =found [0 ]["id"],fields ="id,name,capabilities").execute ()
                handle_sheet (meta ["id"],meta ["capabilities"].get ("canEdit",False ),meta .get ("name",cval ))
            else :
                result ["actions"].append ({"type":"not_found","basename":cval })
        else :
            result ["actions"].append ({"type":"no_link_or_basename"})
    except Exception as e :
        result ["error"]=str (e )
    if not dry_run and csv_path :
        try :
            _safe_delete (csv_path )
        except Exception :
            logger .exception ("Failed to remove uploaded CSV %s",csv_path )
        try :
            base =os .path .abspath (os .path .join (os .path .dirname (__file__ ),'..','..','..','..'))
            for dname in ('tmp_downloads','tmp_uploads','tmp_download','tmp_upload'):
                dpath =os .path .join (base ,dname )
                if os .path .isdir (dpath ):
                    try :
                        shutil .rmtree (dpath )
                        os .makedirs (dpath ,exist_ok =True )
                        logger .info ("Cleared temporary folder %s",dpath )
                    except Exception :
                        logger .exception ("Failed to clear temporary folder %s",dpath )
                else :
                    logger .debug ("Temporary folder not present, skipping: %s",dpath )
        except Exception :
            logger .exception ("Failed to clear temporary folders tmp_downloads/tmp_uploads")
    return result 
def main ():
    import argparse 
    parser =argparse .ArgumentParser ()
    parser .add_argument ("--company",required =True )
    parser .add_argument ("--file",help ="Path to CSV file")
    parser .add_argument ("--apply",action ="store_true",help ="Perform write actions")
    args =parser .parse_args ()
    res =process_company_update (args .company ,csv_path =args .file ,dry_run =not args .apply )
    print (json .dumps (res ,indent =2 ,ensure_ascii =False ))
if __name__ =="__main__":
    main ()