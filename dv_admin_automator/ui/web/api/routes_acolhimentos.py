from fastapi import APIRouter ,HTTPException ,Request 
from fastapi .responses import JSONResponse 
import os 
import csv 
from pathlib import Path 
from datetime import datetime 
from typing import List 
import logging 
try :
    from .sheets_client import read_sheet_rows ,write_row_by_index 
except Exception :
    def read_sheet_rows (sheet_id :str ,range_name :str =None ):
        return None 
    def write_row_by_index (sheet_id :str ,row_index :int ,row_dict :dict )->bool :
        return False 
try :
    from .credentials_cache import get_service_account_info 
    from .credentials_cache import set_service_account_info 
    from .cred_loader import try_auto_load_service_account_from_local 
except Exception :
    def get_service_account_info ():
        return None 
    def set_service_account_info (info ):
        return None 
    def try_auto_load_service_account_from_local ():
        return None 
router =APIRouter ()
logger =logging .getLogger (__name__ )
def _sample_data ():
    now =datetime .utcnow ().isoformat ()
    return [
    {
    "uuid":"1",
    "request_date":"2023-07-07",
    "patient_name":"Erika Oliveira Assis",
    "company":"Queiroz Cavalcanti",
    "collaborator_name":"Colaborador",
    "email":"erikaassis@queirozcavalcanti.adv.br",
    "cpf":"-",
    "phone":"71999213760",
    "project":"Custeio Geral",
    "funding_duration":"Até novo aviso",
    "funding_type":"Semanal",
    "cs_responsible":"Caio",
    "funding_start_month":"2022-07-01",
    "funding_end_month":"",
    "status":"Finalizado",
    "notes":"",
    "rh_responsible":"",
    "last_return_rh":"",
    "last_conference":"",
    "acolhedor":"",
    "last_modified_at":now ,
    "version":1 ,
    },
    {
    "uuid":"2",
    "request_date":"2023-04-05",
    "patient_name":"Maria Rodrigues",
    "company":"Print Comunicação",
    "collaborator_name":"Colaborador",
    "email":"mariarodrigueshang2306@gmail.com",
    "cpf":"-",
    "phone":"24999629189",
    "project":"Custeio Geral",
    "funding_duration":"Até novo aviso",
    "funding_type":"Semanal",
    "cs_responsible":"Caio",
    "funding_start_month":"2023-05-01",
    "funding_end_month":"",
    "status":"Em acolhimento",
    "notes":"teste 09:00",
    "rh_responsible":"João",
    "last_return_rh":"2025-08-29",
    "last_conference":"",
    "acolhedor":"João",
    "last_modified_at":now ,
    "version":1 ,
    },
    ]
def _read_csv (path :str ):
    p =Path (path )
    if not p .exists ():
        return None 
    rows =[]
    with p .open (newline ='',encoding ='utf-8')as fh :
        reader =csv .DictReader (fh )
        for i ,r in enumerate (reader ):
            row ={
            'uuid':r .get ('uuid')or str (i +1 ),
            'request_date':r .get ('Data da Solicitação')or r .get ('request_date')or r .get ('Data')or '',
            'patient_name':r .get ('Nome do paciente')or r .get ('patient_name')or r .get ('Nome')or '',
            'company':r .get ('Empresa')or r .get ('company')or '',
            'collaborator_name':r .get ('Nome do colaborador (Em caso de familiar)')or r .get ('collaborator_name')or '',
            'email':r .get ('E-mail')or r .get ('email')or '',
            'cpf':r .get ('CPF')or r .get ('cpf')or '',
            'phone':r .get ('Telefone')or r .get ('phone')or '',
            'project':r .get ('Projeto vinculado')or r .get ('project')or '',
            'funding_duration':r .get ('Tempo de custeio')or r .get ('funding_duration')or '',
            'funding_type':r .get ('Formato do Custeio')or r .get ('funding_type')or '',
            'cs_responsible':r .get ('CS Responsável')or r .get ('cs_responsible')or '',
            'funding_start_month':r .get ('Mês de Início do Custeio')or r .get ('funding_start_month')or '',
            'funding_end_month':r .get ('Último mês do custeio')or r .get ('funding_end_month')or '',
            'status':r .get ('Status')or r .get ('status')or '',
            'notes':r .get ('Considerações')or r .get ('notes')or '',
            'rh_responsible':r .get ('Responsável do RH)')or r .get ('rh_responsible')or r .get ('Responsável do RH')or '',
            'last_return_rh':r .get ('Ultimo Retono pro RH')or r .get ('last_return_rh')or '',
            'last_conference':r .get ('Última conferência')or r .get ('last_conference')or '',
            'acolhedor':r .get ('Acolhedor')or r .get ('acolhedor')or '',
            'last_modified_at':datetime .utcnow ().isoformat (),
            'version':1 ,
            }
            rows .append (row )
    return rows 
def _read_sheet (sheet_id :str ):
    try :
        raw =read_sheet_rows (sheet_id )
        if not raw :
            return None 
        rows =[]
        for i ,r in enumerate (raw ):
            row ={
            'uuid':r .get ('uuid')or r .get ('ID')or str (i +1 ),
            'request_date':r .get ('Data da Solicitação')or r .get ('request_date')or r .get ('Data')or '',
            'patient_name':r .get ('Nome do paciente')or r .get ('patient_name')or r .get ('Nome')or '',
            'company':r .get ('Empresa')or r .get ('company')or '',
            'collaborator_name':r .get ('Nome do colaborador (Em caso de familiar)')or r .get ('collaborator_name')or '',
            'email':r .get ('E-mail')or r .get ('email')or '',
            'cpf':r .get ('CPF')or r .get ('cpf')or '',
            'phone':r .get ('Telefone')or r .get ('phone')or '',
            'project':r .get ('Projeto vinculado')or r .get ('project')or '',
            'funding_duration':r .get ('Tempo de custeio')or r .get ('funding_duration')or '',
            'funding_type':r .get ('Formato do Custeio')or r .get ('funding_type')or '',
            'cs_responsible':r .get ('CS Responsável')or r .get ('cs_responsible')or '',
            'funding_start_month':r .get ('Mês de Início do Custeio')or r .get ('funding_start_month')or '',
            'funding_end_month':r .get ('Último mês do custeio')or r .get ('funding_end_month')or '',
            'status':r .get ('Status')or r .get ('status')or '',
            'notes':r .get ('Considerações')or r .get ('notes')or '',
            'rh_responsible':r .get ('Responsável do RH)')or r .get ('rh_responsible')or r .get ('Responsável do RH')or '',
            'last_return_rh':r .get ('Ultimo Retono pro RH')or r .get ('last_return_rh')or '',
            'last_conference':r .get ('Última conferência')or r .get ('last_conference')or '',
            'acolhedor':r .get ('Acolhedor')or r .get ('acolhedor')or '',
            'last_modified_at':datetime .utcnow ().isoformat (),
            'version':1 ,
            }
            rows .append (row )
        return rows 
    except Exception :
        return None 
def _attempt_auto_load_credentials ():
    try :
        info =get_service_account_info ()
        if info :
            return True 
        sa =try_auto_load_service_account_from_local ()
        if sa :
            try :
                set_service_account_info (sa )
                return True 
            except Exception :
                return False 
    except Exception :
        return False 
    return False 
def _normalize_header_to_key (h :str ):
    if not h :return None 
    s =h .lower ()
    exact =h .strip ()
    if exact =='Data da Solicitação':
        return 'request_date'
    if exact =='Nome do paciente':
        return 'patient_name'
    if exact =='Empresa':
        return 'company'
    if exact =='Nome do colaborador (Em caso de familiar)':
        return 'collaborator_name'
    if exact =='E-mail':
        return 'email'
    if exact =='CPF':
        return 'cpf'
    if exact =='Telefone':
        return 'phone'
    if exact =='Projeto vinculado':
        return 'project'
    if exact =='Tempo de custeio':
        return 'funding_duration'
    if exact =='Formato do Custeio':
        return 'funding_type'
    if exact =='CS Responsável':
        return 'cs_responsible'
    if exact =='Mês de Início do Custeio':
        return 'funding_start_month'
    if exact =='Último mês do custeio':
        return 'funding_end_month'
    if exact =='Status':
        return 'status'
    if exact =='Considerações':
        return 'notes'
    if exact =='Responsável do RH)'or exact =='Responsável do RH':
        return 'rh_responsible'
    if exact =='Ultimo Retono pro RH':
        return 'last_return_rh'
    if exact =='Última conferência':
        return 'last_conference'
    if exact =='Acolhedor'or exact =='Acolhedor:':
        return 'acolhedor'
    if 'data'in s and 'solicit'in s :return 'request_date'
    if 'nome'in s and 'paciente'in s :return 'patient_name'
    if 'empresa'in s :return 'company'
    if 'colaborador'in s or 'familiar'in s :return 'collaborator_name'
    if 'e-mail'in s or 'email'in s :return 'email'
    if 'cpf'in s :return 'cpf'
    if 'telefone'in s or 'tel'in s :return 'phone'
    if 'projeto'in s :return 'project'
    if 'tempo'in s and 'custeio'in s :return 'funding_duration'
    if 'formato'in s and 'custeio'in s :return 'funding_type'
    if 'cs'in s and 'respons'in s :return 'cs_responsible'
    if ('mês'in s or 'mes'in s )and ('iní'in s or 'ini'in s or 'início'in s ):return 'funding_start_month'
    if 'último'in s and 'custeio'in s :return 'funding_end_month'
    if 'status'in s :return 'status'
    if 'consider'in s or 'observ'in s :return 'notes'
    if 'responsável'in s and 'rh'in s :return 'rh_responsible'
    if 'rh'in s and 'respons'in s :return 'rh_responsible'
    if 'retorno'in s :return 'last_return_rh'
    if 'confer'in s :return 'last_conference'
    if 'acolhedor'in s :return 'acolhedor'
    if 'uuid'in s or 'id'==s .strip ():return 'uuid'
    return None 
@router .get ('/api/acolhimentos')
async def api_acolhimentos_list (request :Request ):
    try :
        sheet_id =os .environ .get ('ACOLH_SHEET_ID')
        logger .info ('api_acolhimentos_list: requested; sheet_id=%s',sheet_id )
        if not sheet_id :
            raise HTTPException (status_code =500 ,detail ='ACOLH_SHEET_ID not configured; integration requires Google Sheet ID')
        rows =_read_sheet (sheet_id )
        if rows is None :
            try :
                if _attempt_auto_load_credentials ():
                    rows =_read_sheet (sheet_id )
            except Exception :
                pass 
            if rows is None :
                info =get_service_account_info ()
                if info is None :
                    logger .warning ('api_acolhimentos_list: credentials locked (no cached credentials and auto-load failed)')
                    raise HTTPException (status_code =423 ,detail ='locked: master password required')
                logger .error ('api_acolhimentos_list: failed to read sheet_id=%s',sheet_id )
                raise HTTPException (status_code =500 ,detail ='Failed to read Google Sheet; check credentials and sheet id')
        return JSONResponse ({'ok':True ,'rows':rows })
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =str (e ))
@router .get ('/api/acolhimentos/{item_id}')
async def api_acolhimento_get (item_id :str ):
    try :
        sheet_id =os .environ .get ('ACOLH_SHEET_ID')
        if not sheet_id :
            raise HTTPException (status_code =500 ,detail ='ACOLH_SHEET_ID not configured')
        rows =_read_sheet (sheet_id )
        if rows is None :
            try :
                if _attempt_auto_load_credentials ():
                    rows =_read_sheet (sheet_id )
            except Exception :
                pass 
            if rows is None :
                info =get_service_account_info ()
                if info is None :
                    logger .warning ('api_acolhimento_get: credentials locked for sheet_id=%s',sheet_id )
                    raise HTTPException (status_code =423 ,detail ='locked: master password required')
                raise HTTPException (status_code =500 ,detail ='Failed to read Google Sheet')
        for i ,r in enumerate (rows ):
            if str (r .get ('uuid'))==str (item_id ):
                return JSONResponse ({'ok':True ,'row':r })
        if item_id .startswith ('row_'):
            try :
                idx =int (item_id .split ('_',1 )[1 ])
                if 0 <=idx and idx <len (rows ):
                    return JSONResponse ({'ok':True ,'row':rows [idx ]})
            except Exception :
                pass 
        raise HTTPException (status_code =404 ,detail ='Registro não encontrado')
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =str (e ))
@router .patch ('/api/acolhimentos/{item_id}')
async def api_acolhimento_patch (item_id :str ,request :Request ):
    try :
        sheet_id =os .environ .get ('ACOLH_SHEET_ID')
        if not sheet_id :
            raise HTTPException (status_code =500 ,detail ='ACOLH_SHEET_ID not configured')
        body =await request .json ()
        changes =dict (body )if isinstance (body ,dict )else {}
        raw_rows =read_sheet_rows (sheet_id )
        if raw_rows is None :
            try :
                if _attempt_auto_load_credentials ():
                    raw_rows =read_sheet_rows (sheet_id )
            except Exception :
                pass 
            if raw_rows is None :
                info =get_service_account_info ()
                if info is None :
                    raise HTTPException (status_code =423 ,detail ='locked: master password required')
                raise HTTPException (status_code =500 ,detail ='Failed to read google sheet')
        norm_rows =_read_sheet (sheet_id )
        if norm_rows is None :
            try :
                if _attempt_auto_load_credentials ():
                    norm_rows =_read_sheet (sheet_id )
            except Exception :
                pass 
            if norm_rows is None :
                info =get_service_account_info ()
                if info is None :
                    raise HTTPException (status_code =423 ,detail ='locked: master password required')
                raise HTTPException (status_code =500 ,detail ='Failed to read google sheet (normalized)')
        target_idx =None 
        for i ,r in enumerate (norm_rows ):
            if str (r .get ('uuid'))==str (item_id ):
                target_idx =i 
                break 
        if target_idx is None and item_id .startswith ('row_'):
            try :
                idx =int (item_id .split ('_',1 )[1 ])
                if 0 <=idx and idx <len (norm_rows ):
                    target_idx =idx 
            except Exception :
                pass 
        if target_idx is None :
            raise HTTPException (status_code =404 ,detail ='Registro não encontrado')
        raw =raw_rows [target_idx ]
        for header in list (raw .keys ()):
            norm =_normalize_header_to_key (header )
            if norm and norm in changes :
                raw [header ]=changes [norm ]
        ok =write_row_by_index (sheet_id ,target_idx ,raw )
        if not ok :
            raise HTTPException (status_code =500 ,detail ='Failed to write to Google Sheet')
        updated_norm_rows =_read_sheet (sheet_id )
        updated_row =updated_norm_rows [target_idx ]if updated_norm_rows else None 
        return JSONResponse ({'ok':True ,'row':updated_row })
    except HTTPException :
        raise 
    except Exception as e :
        raise HTTPException (status_code =500 ,detail =str (e ))