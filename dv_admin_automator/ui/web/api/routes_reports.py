from fastapi import APIRouter ,HTTPException ,Request 
from fastapi .responses import Response ,StreamingResponse ,JSONResponse 
import io 
import csv 
import logging 
import os 
from typing import List ,Dict ,Optional ,Tuple 
from datetime import datetime ,date 
import asyncio 
import uuid 
import time 
import tempfile 
from ..jobs import get_default_manager 
try :
    from dv_admin_automator .browser .pool import get_default_pool 
except Exception :
    get_default_pool =None 
_REPORT_JOB_LOGS :Dict [str ,list ]={}
_REPORT_PUBLIC_TO_INTERNAL :Dict [str ,str ]={}
_REPORT_RESULTS :Dict [str ,str ]={}
logger =logging .getLogger (__name__ )
router =APIRouter ()
try :
    from .routes_acolhimentos import _read_sheet ,_attempt_auto_load_credentials ,get_service_account_info 
except Exception :
    def _read_sheet (sheet_id :str ):
        return None 
    def _attempt_auto_load_credentials ():
        return False 
    def get_service_account_info ():
        return None 
def _parse_date (s :Optional [str ])->Optional [date ]:
    if not s :
        return None 
    s =str (s ).strip ()
    if not s :
        return None 
    try :
        if '/'in s :
            parts =s .split ('/')
            if len (parts )>=3 :
                d =date (int (parts [2 ]),int (parts [1 ]),int (parts [0 ]))
                return d 
    except Exception :
        pass 
    try :
        return datetime .fromisoformat (s ).date ()
    except Exception :
        try :
            return datetime .strptime (s ,'%Y-%m-%d').date ()
        except Exception :
            pass 
    try :
        s2 =s .replace ('a.m.','AM').replace ('p.m.','PM').replace ('a.m','AM').replace ('p.m','PM')
        s2 =s2 .replace ('.','')
        try :
            from dateutil import parser as _dateutil_parser 
            dt =_dateutil_parser .parse (s2 ,dayfirst =False ,fuzzy =True )
            return dt .date ()
        except Exception :
            pass 
        fmts =[
        '%B %d, %Y, %I:%M %p',
        '%b %d, %Y, %I:%M %p',
        '%B %d, %Y',
        '%b %d, %Y',
        '%d %B %Y',
        '%d %b %Y',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        ]
        for f in fmts :
            try :
                return datetime .strptime (s2 ,f ).date ()
            except Exception :
                continue 
    except Exception :
        pass 
    return None 
def _is_acolhimento_appt (appt :Dict )->bool :
    if not appt or not isinstance (appt ,dict ):
        return False 
    needle ='acolhimento'
    keys =('plan','plan_name','product','service','package','title','name','appointment_type')
    for k in keys :
        v =appt .get (k )
        if v and isinstance (v ,str )and needle in v .lower ():
            return True 
    for v in appt .values ():
        if isinstance (v ,str )and needle in v .lower ():
            return True 
    return False 
def _group_and_aggregate (rows :List [Dict [str ,str ]],company :Optional [str ],dfrom :Optional [date ],dto :Optional [date ])->Tuple [List [Dict ],Dict ]:
    filtered =[]
    for r in rows :
        try :
            if company and (str (r .get ('company')or '').strip ()!=str (company ).strip ()):
                continue 
            rd =_parse_date (r .get ('request_date'))
            if dfrom and (not rd or rd <dfrom ):
                continue 
            if dto and (not rd or rd >dto ):
                continue 
            filtered .append (r )
        except Exception :
            continue 
    groups ={}
    for r in filtered :
        key =(r .get ('uuid')or (r .get ('patient_name')or '')+'|'+(r .get ('cpf')or ''))
        if key not in groups :
            groups [key ]=[]
        groups [key ].append (r )
    per_patient =[]
    counts ={
    'total_acolhidos':0 ,
    'em_acolhimento_count':0 ,
    'finalizado_count':0 ,
    }
    for key ,items in groups .items ():
        counts ['total_acolhidos']+=1 
        latest =items [-1 ]
        status =(latest .get ('status')or '').strip ()
        total_consults =len (items )
        completed =sum (1 for it in items if (str (it .get ('status')or '').strip ().lower ()=='finalizado')or (it .get ('last_conference')))
        pending =total_consults -completed 
        first_req =None 
        last_cons =None 
        for it in items :
            d =_parse_date (it .get ('request_date'))
            if d :
                if first_req is None or d <first_req :
                    first_req =d 
            lc =None 
            try :
                lc =_parse_date (it .get ('last_conference'))
            except Exception :
                lc =None 
            if lc :
                if last_cons is None or lc >last_cons :
                    last_cons =lc 
        item_obj ={
        'uuid':latest .get ('uuid')or '',
        'patient_name':latest .get ('patient_name')or '',
        'company':latest .get ('company')or '',
        'email':latest .get ('email')or '',
        'acolhimento_type':(latest .get ('funding_duration')or latest .get ('funding_type')or '').strip (),
        'status':status ,
        'total_consults':total_consults ,
        'completed_consults':completed ,
        'pending_consults':pending ,
        'first_request_date':first_req .isoformat ()if first_req else '',
        'last_consult_date':last_cons .isoformat ()if last_cons else '',
        }
        per_patient .append (item_obj )
        if status in ('Em acolhimento','Consulta experimental'):
            counts ['em_acolhimento_count']+=1 
        if status =='Finalizado':
            counts ['finalizado_count']+=1 
    per_patient .sort (key =lambda x :(x .get ('patient_name')or '').lower ())
    try :
        logger .info ('Grouped %d patients (company=%s) preview: %s',len (per_patient ),company ,[p .get ('patient_name')for p in per_patient [:20 ]])
    except Exception :
        pass 
    try :
        print (f"[reports] Grouped {len (per_patient )} patients for company={company }: {[p .get ('patient_name')for p in per_patient [:20 ]]}")
    except Exception :
        pass 
    return per_patient ,counts 
def _generate_pdf_bytes (per_patient :List [Dict ],summary :Dict ,title :str )->Optional [bytes ]:
    try :
        from reportlab .lib .pagesizes import A4 
        from reportlab .platypus import SimpleDocTemplate ,Paragraph ,Spacer ,Table ,TableStyle 
        from reportlab .lib import colors 
        from reportlab .lib .styles import getSampleStyleSheet ,ParagraphStyle 
        from reportlab .lib .units import mm 
    except ImportError :
        logger .warning ("ReportLab não está disponível; geração de PDF desativada.")
        return None 
    buffer =io .BytesIO ()
    doc =SimpleDocTemplate (
    buffer ,
    pagesize =A4 ,
    leftMargin =18 *mm ,
    rightMargin =18 *mm ,
    topMargin =18 *mm ,
    bottomMargin =18 *mm 
    )
    styles =getSampleStyleSheet ()
    COLORS ={
    "light_gray":colors .HexColor ("#f5f5f5"),
    "blue":colors .HexColor ("#cfe2f3"),
    "pink":colors .HexColor ("#fbcfe8"),
    "muted":colors .HexColor ("#6b6b7a"),
    "border":colors .HexColor ("#e9edf2"),
    "text_dark":colors .HexColor ("#102a43"),
    "bg":colors .HexColor ("#ffffff"),
    }
    style_title =ParagraphStyle ("title",parent =styles ["Heading1"],fontName ="Helvetica-Bold",fontSize =16 ,textColor =COLORS ["text_dark"])
    style_meta =ParagraphStyle ("meta",parent =styles ["Normal"],fontName ="Helvetica",fontSize =9 ,textColor =COLORS ["muted"])
    style_normal =ParagraphStyle ("normal",parent =styles ["Normal"],fontName ="Helvetica",fontSize =10 ,textColor =COLORS ["text_dark"],wordWrap ='LTR')
    style_normal_name =ParagraphStyle ("normal_name",parent =style_normal ,fontSize =9 )
    style_header =ParagraphStyle ("header",parent =styles ["Normal"],fontName ="Helvetica-Bold",fontSize =9 ,textColor =COLORS ["text_dark"],wordWrap ='LTR')
    style_card_title =ParagraphStyle ("card_title",parent =styles ["Normal"],fontName ="Helvetica-Bold",fontSize =12 ,textColor =COLORS ["text_dark"])
    elements =[]
    elements .append (Paragraph (title ,style_title ))
    elements .append (Spacer (1 ,8 ))
    try :
        total_acolhidos =len (per_patient )
        total_consults =sum (int (p .get ('total_consults')or 0 )for p in per_patient )
        status_counts ={}
        for p in per_patient :
            s =(p .get ('status')or 'Desconhecido').strip ()
            status_counts [s ]=status_counts .get (s ,0 )+1 
        status_items =[f"{k }: {v }"for k ,v in status_counts .items ()if v >0 ]
        status_text =', '.join (status_items )if status_items else '—'
        style_card_label =ParagraphStyle ('card_label',parent =styles ['Normal'],fontName ='Helvetica-Bold',fontSize =9 ,textColor =COLORS ['text_dark'])
        style_card_value =ParagraphStyle ('card_value',parent =styles ['Normal'],fontName ='Helvetica-Bold',fontSize =14 ,textColor =COLORS ['text_dark'],alignment =1 )
        c1 =Paragraph (f"<b>Quantidade de acolhidos</b><br/><font size=14>{total_acolhidos }</font>",style_card_label )
        c2 =Paragraph (f"<b>Consultas totais</b><br/><font size=14>{total_consults }</font>",style_card_label )
        c3 =Paragraph (f"<b>Acolhidos por Status</b><br/><font size=9>{status_text }</font>",style_card_label )
        cards_tbl =Table ([[c1 ,c2 ,c3 ]],colWidths =[doc .width /3.0 ]*3 )
        cards_tbl .setStyle (TableStyle ([
        ('BACKGROUND',(0 ,0 ),(0 ,0 ),COLORS ['blue']),
        ('BACKGROUND',(1 ,0 ),(1 ,0 ),COLORS ['pink']),
        ('BACKGROUND',(2 ,0 ),(2 ,0 ),COLORS ['light_gray']),
        ('VALIGN',(0 ,0 ),(-1 ,-1 ),'MIDDLE'),
        ('ALIGN',(0 ,0 ),(-1 ,-1 ),'CENTER'),
        ('INNERGRID',(0 ,0 ),(-1 ,-1 ),0.25 ,COLORS ['border']),
        ('BOX',(0 ,0 ),(-1 ,-1 ),0.25 ,COLORS ['border']),
        ('PADDING',(0 ,0 ),(-1 ,-1 ),8 ),
        ]))
        elements .append (cards_tbl )
        elements .append (Spacer (1 ,10 ))
    except Exception :
        pass 
    def _fmt_date (iso_str :Optional [str ])->str :
        if not iso_str :return "—"
        for fmt in ("%Y-%m-%d","%Y-%m-%dT%H:%M:%S","%Y-%m-%dT%H:%M:%S.%f"):
            try :return datetime .strptime (iso_str ,fmt ).strftime ("%d/%m/%Y")
            except ValueError :continue 
        return iso_str 
    def _build_card (patients :List [Dict ],label :str ,color )->list :
        elems =[]
        header =Table ([[Paragraph (label ,style_card_title )]],colWidths =[doc .width ])
        header .setStyle (TableStyle ([("BACKGROUND",(0 ,0 ),(-1 ,-1 ),color ),("VALIGN",(0 ,0 ),(-1 ,-1 ),"MIDDLE"),("PADDING",(0 ,0 ),(-1 ,-1 ),6 )]))
        elems .append (header )
        elems .append (Spacer (1 ,4 ))
        elems .append (Paragraph (f"Total: {len (patients )}",style_card_title ))
        elems .append (Spacer (1 ,6 ))
        col_widths =[
        doc .width *0.26 ,
        doc .width *0.10 ,
        doc .width *0.12 ,
        doc .width *0.13 ,
        doc .width *0.13 ,
        doc .width *0.13 ,
        doc .width *0.13 ,
        ]
        headers =["Nome","Status","Consultas","Realizadas","Pendentes","1ª consulta","Última consulta"]
        rows =[[Paragraph (h ,style_header )for h in headers ]]
        for p in patients :
            rows .append ([
            Paragraph (p .get ("patient_name",""),style_normal_name ),
            Paragraph (p .get ("status",""),style_normal ),
            Paragraph (str (p .get ("total_consults",0 )),style_normal ),
            Paragraph (str (p .get ("completed_consults",0 )),style_normal ),
            Paragraph (str (p .get ("pending_consults",0 )),style_normal ),
            Paragraph (_fmt_date (p .get ("first_request_date")),style_normal ),
            Paragraph (_fmt_date (p .get ("last_consult_date")),style_normal )
            ])
        tbl =Table (rows ,colWidths =col_widths ,repeatRows =1 )
        tbl .setStyle (TableStyle ([
        ("GRID",(0 ,0 ),(-1 ,-1 ),0.5 ,COLORS ["border"]),
        ("BACKGROUND",(0 ,0 ),(-1 ,0 ),COLORS ["light_gray"]),
        ("ALIGN",(2 ,1 ),(4 ,-1 ),"CENTER"),
        ("ALIGN",(5 ,1 ),(6 ,-1 ),"CENTER"),
        ("VALIGN",(0 ,0 ),(-1 ,-1 ),"TOP"),
        ("PADDING",(0 ,0 ),(-1 ,-1 ),4 ),
        ]))
        elems .append (tbl )
        elems .append (Spacer (1 ,12 ))
        return elems 
    em_acolhimento =[p for p in per_patient if (p .get ("status")or "").lower ()in ("em acolhimento","consulta experimental")]
    finalizados =[p for p in per_patient if (p .get ("status")or "").lower ()=="finalizado"]
    elements +=_build_card (em_acolhimento ,"Pacientes em acolhimento:",COLORS ["blue"])
    elements +=_build_card (finalizados ,"Pacientes com acolhimentos finalizados:",COLORS ["pink"])
    elements .append (Paragraph (f"Gerado em {datetime .now ().strftime ('%d/%m/%Y %H:%M:%S')}",style_meta ))
    try :
        doc .build (elements )
        buffer .seek (0 )
        return buffer .read ()
    except Exception as e :
        logger .error (f"Falha ao gerar PDF: {e }")
        return None 
@router .get ('/api/reports/company')
async def api_report_company (request :Request ):
    def _append_log (job_id :str ,msg :str ):
        try :
            _REPORT_JOB_LOGS .setdefault (job_id ,[]).append (f"[{time .strftime ('%Y-%m-%d %H:%M:%S')}] {msg }")
        except Exception :
            pass 
    def _read_rows_or_error ():
        sheet_id =os .environ .get ('ACOLH_SHEET_ID')
        if not sheet_id :
            raise HTTPException (status_code =500 ,detail ='ACOLH_SHEET_ID not configured')
        rows =_read_sheet (sheet_id )
        if rows is None :
            if _attempt_auto_load_credentials ():
                rows =_read_sheet (sheet_id )
        if rows is None :
            info =get_service_account_info ()
            if info is None :
                raise HTTPException (status_code =423 ,detail ='locked: master password required')
            raise HTTPException (status_code =500 ,detail ='Failed to read Google Sheet')
        return rows 
    def _ensure_browser_session_if_requested (pool ,session_id :Optional [str ]):
        if not session_id or not pool :
            return 
        try :
            if pool .get_manager (session_id )is None :
                raise HTTPException (status_code =404 ,detail =f"Requested browser_session_id='{session_id }' has no active session",)
        except HTTPException :
            raise 
        except Exception :
            return 
    async def _enrich_per_patient_sync (per_patient :List [Dict ],manager_for_request ):
        try :
            from dv_admin_automator .backend .appointments import get_participant_history 
        except Exception :
            get_participant_history =None 
        loop =asyncio .get_running_loop ()
        for p in per_patient :
            try :
                email =(p .get ('email')or '').strip ()
                name =(p .get ('patient_name')or '').strip ()
                logger .info ('Enrich sync -> patient=%s email=%s',name or '<no-name>',email or '<no-email>')
                try :
                    print (f"[reports] Enrich sync -> patient={name or '<no-name>'} email={email or '<no-email>'}")
                except Exception :
                    pass 
                if not email :
                    p ['appointment_note']='Sem e-mail informado'
                    p ['total_consults']=0 
                    p ['completed_consults']=0 
                    p ['pending_consults']=0 
                    p ['first_request_date']=''
                    p ['last_consult_date']=''
                    continue 
                if get_participant_history is None :
                    p ['appointment_note']='Sem histórico atrelado'
                    p ['total_consults']=0 
                    p ['completed_consults']=0 
                    p ['pending_consults']=0 
                    p ['first_request_date']=''
                    p ['last_consult_date']=''
                    continue 
                try :
                    if manager_for_request is not None :
                        history =await loop .run_in_executor (None ,lambda e =email ,m =manager_for_request :get_participant_history (e ,manager =m ))
                    else :
                        history =await loop .run_in_executor (None ,lambda e =email :get_participant_history (e ))
                except Exception :
                    logger .exception ('Error fetching history for email %s',email )
                    p ['appointment_note']='Sem histórico atrelado'
                    p ['total_consults']=0 
                    p ['completed_consults']=0 
                    p ['pending_consults']=0 
                    continue 
                if not history or not isinstance (history ,dict )or not history .get ('appointments'):
                    p ['appointment_note']='Sem histórico atrelado'
                    p ['total_consults']=0 
                    p ['completed_consults']=0 
                    p ['pending_consults']=0 
                    logger .info ('No history for %s <%s>',name or '<no-name>',email or '<no-email>')
                    try :
                        print (f"[reports] No history for {name or '<no-name>'} <{email or '<no-email>'}>")
                    except Exception :
                        pass 
                    continue 
                appts =history .get ('appointments')or []
                acolh_appts =[a for a in appts if _is_acolhimento_appt (a )]
                total =len (acolh_appts )
                completed =0 
                now =datetime .utcnow ()
                for a in acolh_appts :
                    st =(a .get ('status')or '').lower ()
                    if 'realiz'in st or 'realizada'in st or 'realizado'in st :
                        completed +=1 
                    else :
                        try :
                            sd =None 
                            if a .get ('schedule'):
                                sd =_parse_date (a .get ('schedule'))
                            if sd and isinstance (sd ,date )and sd <=now .date ():
                                completed +=1 
                        except Exception :
                            pass 
                pending =max (0 ,total -completed )
                p ['total_consults']=total 
                p ['completed_consults']=completed 
                p ['pending_consults']=pending 
                try :
                    raw_samples =[]
                    parsed_dates =[]
                    for a in appts :
                        for k in ('schedule','date','consultation_date','data','datetime','started_at','ended_at'):
                            if a .get (k ):
                                raw_samples .append ((k ,a .get (k )))
                                break 
                    raw_samples =raw_samples [:8 ]
                    for a in appts :
                        d =None 
                        for k in ('schedule','date','consultation_date','data','datetime','started_at','ended_at'):
                            if a .get (k ):
                                d =_parse_date (a .get (k ))
                                if d :
                                    parsed_dates .append (d )
                                    break 
                    if parsed_dates :
                        parsed_dates .sort ()
                        p ['first_request_date']=parsed_dates [0 ].isoformat ()
                        p ['last_consult_date']=parsed_dates [-1 ].isoformat ()
                    try :
                        logger .info ('Parsed dates for %s (email=%s): raw_samples=%s parsed=%s',name or '<no-name>',email or '<no-email>',[(k ,str (v ))for k ,v in raw_samples ],[d .isoformat ()for d in parsed_dates ])
                        try :
                            print (f"[reports] Parsed dates for {name or '<no-name>'} <{email or '<no-email>'}>: raw_samples={[(k ,str (v ))for k ,v in raw_samples ]} parsed={[d .isoformat ()for d in parsed_dates ]}")
                        except Exception :
                            pass 
                    except Exception :
                        pass 
                except Exception :
                    pass 
                p ['appointment_note']=''
                try :
                    logger .info ('Enriched sync -> %s: total=%s completed=%s pending=%s first=%s last=%s',
                    name or '<no-name>',p .get ('total_consults'),p .get ('completed_consults'),p .get ('pending_consults'),
                    p .get ('first_request_date')or '-',p .get ('last_consult_date')or '-')
                    try :
                        print (f"[reports] Enriched sync -> {name or '<no-name>'}: total={p .get ('total_consults')} completed={p .get ('completed_consults')} pending={p .get ('pending_consults')} first={p .get ('first_request_date')or '-'} last={p .get ('last_consult_date')or '-'}")
                    except Exception :
                        pass 
                except Exception :
                    pass 
            except Exception :
                p ['appointment_note']='Sem histórico atrelado'
                p ['total_consults']=0 
                p ['completed_consults']=0 
                p ['pending_consults']=0 
                p ['first_request_date']=''
                p ['last_consult_date']=''
    def _create_and_submit_async_job (public_job_id :str ,per_patient :List [Dict ],summary :Dict ,company :str ,fmt :str ,
    req_headless :bool ,req_browser_session :Optional [str ],req_username :Optional [str ],req_password :Optional [str ]):
        _REPORT_JOB_LOGS .setdefault (public_job_id ,[]).append ('Report generation requested')
        def _job ():
            pool =get_default_pool ()if get_default_pool else None 
            created_session =None 
            manager_for_job =None 
            try :
                _append_log (public_job_id ,'job started')
                try :
                    from dv_admin_automator .backend .appointments import get_participant_history 
                except Exception :
                    get_participant_history =None 
                try :
                    if pool and req_browser_session :
                        mgr =pool .get_manager (req_browser_session )
                        if mgr :
                            manager_for_job =mgr 
                            _append_log (public_job_id ,f'using existing browser session {req_browser_session }')
                    if pool and (manager_for_job is None )and req_headless :
                        created_session =pool .create_session (headless =True )
                        manager_for_job =pool .get_manager (created_session )
                        _append_log (public_job_id ,f'created browser session {created_session } (headless)')
                        try :
                            from dv_admin_automator .ui .web .api import routes_auth as auth_routes 
                            username =req_username 
                            password =req_password 
                            if username and password :
                                try :
                                    auth_routes ._SESSION_CREDENTIALS [created_session ]={'username':username ,'password':password ,'headless':True }
                                except Exception :
                                    pass 
                                try :
                                    auth_routes ._login_job (created_session ,username ,password ,True )
                                    _append_log (public_job_id ,f'performed login for session {created_session }')
                                except Exception as e :
                                    _append_log (public_job_id ,f'login job failed for session {created_session }: {e }')
                        except Exception :
                            _append_log (public_job_id ,'login-setup failed for created session')
                except Exception as e :
                    _append_log (public_job_id ,f'failed to create/use browser session: {e }')
                    created_session =None 
                if get_participant_history is None :
                    for p in per_patient :
                        p ['appointment_note']='Sem histórico atrelado'
                        p ['total_consults']=0 
                        p ['completed_consults']=0 
                        p ['pending_consults']=0 
                else :
                    for p in per_patient :
                        try :
                            email =(p .get ('email')or '').strip ()
                            name =(p .get ('patient_name')or '').strip ()
                            _append_log (public_job_id ,f'enrich async -> patient={name or "<no-name>"} email={email or "<no-email>"}')
                            logger .info ('Enrich async -> patient=%s email=%s (job=%s)',name or '<no-name>',email or '<no-email>',public_job_id )
                            try :
                                print (f"[reports] Enrich async -> patient={name or '<no-name>'} email={email or '<no-email>'} (job={public_job_id })")
                            except Exception :
                                pass 
                            if not email :
                                p ['appointment_note']='Sem e-mail informado'
                                p ['total_consults']=0 
                                p ['completed_consults']=0 
                                p ['pending_consults']=0 
                                p ['first_request_date']=''
                                p ['last_consult_date']=''
                                continue 
                            try :
                                if manager_for_job is not None :
                                    history =get_participant_history (email ,manager =manager_for_job )
                                else :
                                    history =get_participant_history (email )
                            except Exception :
                                try :
                                    history =get_participant_history (email )
                                except Exception :
                                    history =None 
                            if not history or not isinstance (history ,dict )or not history .get ('appointments'):
                                p ['appointment_note']='Sem histórico atrelado'
                                p ['total_consults']=0 
                                p ['completed_consults']=0 
                                p ['pending_consults']=0 
                                p ['first_request_date']=''
                                p ['last_consult_date']=''
                                _append_log (public_job_id ,f'no history for {name or "<no-name>"} <{email or "<no-email>"}>')
                                logger .info ('No history for %s <%s> (job=%s)',name or '<no-name>',email or '<no-email>',public_job_id )
                                try :
                                    print (f"[reports] No history for {name or '<no-name>'} <{email or '<no-email>'}> (job={public_job_id })")
                                except Exception :
                                    pass 
                                continue 
                            appts =history .get ('appointments')or []
                            acolh_appts =[a for a in appts if _is_acolhimento_appt (a )]
                            total =len (acolh_appts )
                            completed =0 
                            now_dt =datetime .utcnow ()
                            for a in acolh_appts :
                                st =(a .get ('status')or '').lower ()
                                if 'realiz'in st or 'realizada'in st or 'realizado'in st :
                                    completed +=1 
                                else :
                                    try :
                                        sd =None 
                                        if a .get ('schedule'):
                                            sd =_parse_date (a .get ('schedule'))
                                        if sd and isinstance (sd ,date )and sd <=now_dt .date ():
                                            completed +=1 
                                    except Exception :
                                        pass 
                            pending =max (0 ,total -completed )
                            p ['total_consults']=total 
                            p ['completed_consults']=completed 
                            p ['pending_consults']=pending 
                            try :
                                raw_samples =[]
                                parsed_dates =[]
                                for a in appts :
                                    for k in ('schedule','date','consultation_date','data','datetime','started_at','ended_at'):
                                        if a .get (k ):
                                            raw_samples .append ((k ,a .get (k )))
                                            break 
                                raw_samples =raw_samples [:8 ]
                                for a in appts :
                                    for k in ('schedule','date','consultation_date','data','datetime','started_at','ended_at'):
                                        if a .get (k ):
                                            d =_parse_date (a .get (k ))
                                            if d :
                                                parsed_dates .append (d )
                                                break 
                                if parsed_dates :
                                    parsed_dates .sort ()
                                    p ['first_request_date']=parsed_dates [0 ].isoformat ()
                                    p ['last_consult_date']=parsed_dates [-1 ].isoformat ()
                                try :
                                    logger .info ('Parsed dates (async job) for %s (email=%s): raw_samples=%s parsed=%s (job=%s)',name or '<no-name>',email or '<no-email>',[(k ,str (v ))for k ,v in raw_samples ],[d .isoformat ()for d in parsed_dates ],public_job_id )
                                    try :
                                        print (f"[reports] Parsed dates (async job={public_job_id }) for {name or '<no-name>'} <{email or '<no-email>'}>: raw_samples={[(k ,str (v ))for k ,v in raw_samples ]} parsed={[d .isoformat ()for d in parsed_dates ]}")
                                    except Exception :
                                        pass 
                                except Exception :
                                    pass 
                            except Exception :
                                pass 
                            p ['appointment_note']=''
                            try :
                                _append_log (public_job_id ,f'enriched {name or "<no-name>"}: total={p .get ("total_consults")} completed={p .get ("completed_consults")} first={p .get ("first_request_date")or "-"} last={p .get ("last_consult_date")or "-"}')
                                logger .info ('Enriched async -> %s: total=%s completed=%s first=%s last=%s (job=%s)',
                                name or '<no-name>',p .get ('total_consults'),p .get ('completed_consults'),p .get ('first_request_date')or '-',p .get ('last_consult_date')or '-',public_job_id )
                                try :
                                    print (f"[reports] Enriched async -> {name or '<no-name>'}: total={p .get ('total_consults')} completed={p .get ('completed_consults')} first={p .get ('first_request_date')or '-'} last={p .get ('last_consult_date')or '-'} (job={public_job_id })")
                                except Exception :
                                    pass 
                            except Exception :
                                pass 
                        except Exception :
                            p ['appointment_note']='Sem histórico atrelado'
                            p ['total_consults']=0 
                            p ['completed_consults']=0 
                            p ['pending_consults']=0 
                if fmt =='csv':
                    data =_generate_csv_bytes (per_patient )
                    ext ='csv'
                else :
                    pdf =_generate_pdf_bytes (per_patient ,summary ,f'Relatório de Acolhimentos - {company }')
                    if pdf is None :
                        _append_log (public_job_id ,'PDF generation not available')
                        return False 
                    data =pdf 
                    ext ='pdf'
                base =os .path .join (os .getcwd (),'tmp_uploads')
                os .makedirs (base ,exist_ok =True )
                fname =f"{public_job_id }_{company .strip ().replace (' ','_')}.{ext }"
                path =os .path .join (base ,fname )
                with open (path ,'wb')as fh :
                    fh .write (data )
                _REPORT_RESULTS [public_job_id ]=fname 
                _append_log (public_job_id ,f'written {path }')
                return True 
            except Exception as e :
                _append_log (public_job_id ,f'job exception: {e }')
                return False 
            finally :
                try :
                    if pool and created_session :
                        pool .close_session (created_session )
                        _append_log (public_job_id ,f'closed browser session {created_session }')
                except Exception :
                    pass 
        internal =get_default_manager ().submit (_job )
        _REPORT_PUBLIC_TO_INTERNAL [public_job_id ]=internal 
        _REPORT_JOB_LOGS .setdefault (public_job_id ,[]).append (f'submitted internal job {internal }')
        return internal 
    try :
        company =request .query_params .get ('company')
        fmt =(request .query_params .get ('format')or 'csv').lower ()
        date_from =_parse_date (request .query_params .get ('date_from'))
        date_to =_parse_date (request .query_params .get ('date_to'))
        if not company :
            raise HTTPException (status_code =400 ,detail ='company parameter required')
        rows =_read_rows_or_error ()
        per_patient ,summary =_group_and_aggregate (rows ,company ,date_from ,date_to )
        async_pref =(request .query_params .get ('async')or '').lower ()in ('1','true','yes')
        req_headless =(request .query_params .get ('headless')or '').lower ()in ('1','true','yes')
        req_browser_session =request .query_params .get ('browser_session_id')
        pool =get_default_pool ()if get_default_pool else None 
        if req_browser_session and pool :
            try :
                if pool .get_manager (req_browser_session )is None :
                    return JSONResponse ({'ok':False ,'error':'no_active_browser_session','message':f"Requested browser_session_id='{req_browser_session }' has no active session"},status_code =404 )
            except Exception :
                pass 
        try :
            req_username =request .session .get ('moodar_username')if hasattr (request ,'session')else None 
            req_password =request .session .get ('moodar_password')if hasattr (request ,'session')else None 
        except Exception :
            req_username =None ;req_password =None 
        if not async_pref and len (per_patient )>200 :
            async_pref =True 
        if async_pref :
            public_job_id ='report:'+uuid .uuid4 ().hex [:10 ]
            internal =_create_and_submit_async_job (public_job_id ,per_patient ,summary ,company ,fmt ,req_headless ,req_browser_session ,req_username ,req_password )
            return JSONResponse ({'ok':True ,'job_id':public_job_id })
        try :
            from dv_admin_automator .backend .appointments import get_participant_history 
        except Exception :
            get_participant_history =None 
        manager_for_request =None 
        try :
            if pool and req_browser_session :
                mgr =pool .get_manager (req_browser_session )
                if mgr :
                    manager_for_request =mgr 
        except Exception :
            manager_for_request =None 
        await _enrich_per_patient_sync (per_patient ,manager_for_request )
        try :
            logger .debug ('Per-patient dates after enrichment (company=%s): %s',company ,[(p .get ('patient_name'),p .get ('first_request_date'),p .get ('last_consult_date'))for p in per_patient ])
        except Exception :
            pass 
        filename_base =f"Relatorio_{company .strip ().replace (' ','_')}"
        if fmt =='csv':
            data =_generate_csv_bytes (per_patient )
            headers ={'Content-Disposition':f'attachment; filename="{filename_base }.csv"'}
            return Response (content =data ,media_type ='text/csv',headers =headers )
        elif fmt =='pdf':
            pdf =_generate_pdf_bytes (per_patient ,summary ,f'Relatório - {company }')
            if pdf is None :
                raise HTTPException (status_code =501 ,detail ='PDF generation not available (reportlab missing)')
            headers ={'Content-Disposition':f'attachment; filename="{filename_base }.pdf"'}
            return Response (content =pdf ,media_type ='application/pdf',headers =headers )
        else :
            raise HTTPException (status_code =400 ,detail ='Unsupported format')
    except HTTPException :
        raise 
    except Exception as e :
        logger .exception ('api_report_company error')
        raise HTTPException (status_code =500 ,detail =str (e ))
@router .get ('/api/reports/general')
async def api_report_general (request :Request ):
    try :
        fmt =(request .query_params .get ('format')or 'csv').lower ()
        date_from =_parse_date (request .query_params .get ('date_from'))
        date_to =_parse_date (request .query_params .get ('date_to'))
        sheet_id =os .environ .get ('ACOLH_SHEET_ID')
        if not sheet_id :
            raise HTTPException (status_code =500 ,detail ='ACOLH_SHEET_ID not configured')
        rows =_read_sheet (sheet_id )
        if rows is None :
            if _attempt_auto_load_credentials ():
                rows =_read_sheet (sheet_id )
        if rows is None :
            info =get_service_account_info ()
            if info is None :
                raise HTTPException (status_code =423 ,detail ='locked: master password required')
            raise HTTPException (status_code =500 ,detail ='Failed to read Google Sheet')
        per_patient ,summary =_group_and_aggregate (rows ,None ,date_from ,date_to )
        async_pref =(request .query_params .get ('async')or '').lower ()in ('1','true','yes')
        req_headless =(request .query_params .get ('headless')or '').lower ()in ('1','true','yes')
        req_browser_session =request .query_params .get ('browser_session_id')
        pool =get_default_pool ()if get_default_pool else None 
        if req_browser_session and pool :
            try :
                if pool .get_manager (req_browser_session )is None :
                    return JSONResponse ({'ok':False ,'error':'no_active_browser_session','message':f"Requested browser_session_id='{req_browser_session }' has no active session"},status_code =404 )
            except Exception :
                pass 
        try :
            req_username =request .session .get ('moodar_username')if hasattr (request ,'session')else None 
            req_password =request .session .get ('moodar_password')if hasattr (request ,'session')else None 
        except Exception :
            req_username =None ;req_password =None 
        if not async_pref and len (per_patient )>200 :
            async_pref =True 
        def _append_log (job_id :str ,msg :str ):
            try :
                _REPORT_JOB_LOGS .setdefault (job_id ,[]).append (f"[{time .strftime ('%Y-%m-%d %H:%M:%S')}] {msg }")
            except Exception :
                pass 
        if async_pref :
            public_job_id ='report:'+uuid .uuid4 ().hex [:10 ]
            _REPORT_JOB_LOGS .setdefault (public_job_id ,[]).append ('Report generation requested')
            def _job ():
                pool =get_default_pool ()if get_default_pool else None 
                created_session =None 
                manager_for_job =None 
                try :
                    _append_log (public_job_id ,'job started')
                    try :
                        from dv_admin_automator .backend .appointments import get_participant_history 
                    except Exception :
                        get_participant_history =None 
                    try :
                        if pool and req_browser_session :
                            mgr =pool .get_manager (req_browser_session )
                            if mgr :
                                manager_for_job =mgr 
                                _append_log (public_job_id ,f'using existing browser session {req_browser_session }')
                        if pool and (manager_for_job is None )and req_headless :
                            try :
                                created_session =pool .create_session (headless =True )
                                manager_for_job =pool .get_manager (created_session )
                                _append_log (public_job_id ,f'created browser session {created_session } (headless)')
                                try :
                                    from dv_admin_automator .ui .web .api import routes_auth as auth_routes 
                                    username =req_username 
                                    password =req_password 
                                    if username and password :
                                        try :
                                            try :
                                                auth_routes ._SESSION_CREDENTIALS [created_session ]={'username':username ,'password':password ,'headless':True }
                                            except Exception :
                                                pass 
                                            try :
                                                auth_routes ._login_job (created_session ,username ,password ,True )
                                                _append_log (public_job_id ,f'performed login for session {created_session }')
                                            except Exception as e :
                                                _append_log (public_job_id ,f'login job failed for session {created_session }: {e }')
                                        except Exception :
                                            pass 
                                except Exception :
                                    pass 
                            except Exception as e :
                                _append_log (public_job_id ,f'failed to create browser session: {e }')
                                created_session =None 
                    except Exception :
                        pass 
                    for p in per_patient :
                        try :
                            email =(p .get ('email')or '').strip ()
                            name =(p .get ('patient_name')or '').strip ()
                            _append_log (public_job_id ,f'enrich async (general) -> patient={name or "<no-name>"} email={email or "<no-email>"}')
                            logger .info ('Enrich async (general) -> patient=%s email=%s (job=%s)',name or '<no-name>',email or '<no-email>',public_job_id )
                            try :
                                print (f"[reports] Enrich async (general) -> patient={name or '<no-name>'} email={email or '<no-email>'} (job={public_job_id })")
                            except Exception :
                                pass 
                            if not email :
                                p ['appointment_note']='Sem e-mail informado'
                                p ['total_consults']=0 
                                p ['completed_consults']=0 
                                p ['pending_consults']=0 
                                p ['first_request_date']=''
                                p ['last_consult_date']=''
                                continue 
                            if get_participant_history is None :
                                p ['appointment_note']='Sem histórico atrelado'
                                p ['total_consults']=0 
                                p ['completed_consults']=0 
                                p ['pending_consults']=0 
                                p ['first_request_date']=''
                                p ['last_consult_date']=''
                                continue 
                            history =None 
                            try :
                                if manager_for_job is not None :
                                    history =get_participant_history (email ,manager =manager_for_job )
                                else :
                                    history =get_participant_history (email )
                            except Exception :
                                try :
                                    history =get_participant_history (email )
                                except Exception :
                                    history =None 
                            if not history or not isinstance (history ,dict )or not history .get ('appointments'):
                                p ['appointment_note']='Sem histórico atrelado'
                                p ['total_consults']=0 
                                p ['completed_consults']=0 
                                p ['pending_consults']=0 
                                _append_log (public_job_id ,f'no history for {name or "<no-name>"} <{email or "<no-email>"}>')
                                logger .info ('No history for %s <%s> (general job=%s)',name or '<no-name>',email or '<no-email>',public_job_id )
                                try :
                                    print (f"[reports] No history for {name or '<no-name>'} <{email or '<no-email>'}> (general job={public_job_id })")
                                except Exception :
                                    pass 
                                continue 
                            appts =history .get ('appointments')or []
                            acolh_appts =[a for a in appts if _is_acolhimento_appt (a )]
                            total =len (acolh_appts )
                            completed =0 
                            now_dt =datetime .utcnow ()
                            for a in acolh_appts :
                                st =(a .get ('status')or '').lower ()
                                if 'realiz'in st or 'realizada'in st or 'realizado'in st :
                                    completed +=1 
                                else :
                                    try :
                                        sd =None 
                                        if a .get ('schedule'):
                                            sd =_parse_date (a .get ('schedule'))
                                        if sd and isinstance (sd ,date )and sd <=now_dt .date ():
                                            completed +=1 
                                    except Exception :
                                        pass 
                            pending =max (0 ,total -completed )
                            p ['total_consults']=total 
                            p ['completed_consults']=completed 
                            p ['pending_consults']=pending 
                            try :
                                raw_samples =[]
                                parsed_dates =[]
                                for a in appts :
                                    for k in ('schedule','date','consultation_date','data','datetime','started_at','ended_at'):
                                        if a .get (k ):
                                            raw_samples .append ((k ,a .get (k )))
                                            break 
                                raw_samples =raw_samples [:8 ]
                                for a in appts :
                                    for k in ('schedule','date','consultation_date','data','datetime','started_at','ended_at'):
                                        if a .get (k ):
                                            d =_parse_date (a .get (k ))
                                            if d :
                                                parsed_dates .append (d )
                                                break 
                                if parsed_dates :
                                    parsed_dates .sort ()
                                    p ['first_request_date']=parsed_dates [0 ].isoformat ()
                                    p ['last_consult_date']=parsed_dates [-1 ].isoformat ()
                                try :
                                    logger .info ('Parsed dates (general async) for %s (email=%s): raw_samples=%s parsed=%s (job=%s)',name or '<no-name>',email or '<no-email>',[(k ,str (v ))for k ,v in raw_samples ],[d .isoformat ()for d in parsed_dates ],public_job_id )
                                    try :
                                        print (f"[reports] Parsed dates (general job={public_job_id }) for {name or '<no-name>'} <{email or '<no-email>'}>: raw_samples={[(k ,str (v ))for k ,v in raw_samples ]} parsed={[d .isoformat ()for d in parsed_dates ]}")
                                    except Exception :
                                        pass 
                                except Exception :
                                    pass 
                            except Exception :
                                pass 
                            p ['appointment_note']=''
                            try :
                                _append_log (public_job_id ,f'enriched {name or "<no-name>"}: total={p .get ("total_consults")} completed={p .get ("completed_consults")} first={p .get ("first_request_date")or "-"} last={p .get ("last_consult_date")or "-"}')
                                logger .info ('Enriched async (general) -> %s: total=%s completed=%s first=%s last=%s (job=%s)',
                                name or '<no-name>',p .get ('total_consults'),p .get ('completed_consults'),p .get ('first_request_date')or '-',p .get ('last_consult_date')or '-',public_job_id )
                                try :
                                    print (f"[reports] Enriched async (general) -> {name or '<no-name>'}: total={p .get ('total_consults')} completed={p .get ('completed_consults')} first={p .get ('first_request_date')or '-'} last={p .get ('last_consult_date')or '-'} (general job={public_job_id })")
                                except Exception :
                                    pass 
                            except Exception :
                                pass 
                        except Exception as e :
                            _append_log (public_job_id ,f'patient {p .get ("patient_name")}: error {e }')
                            p ['appointment_note']='Sem histórico atrelado'
                            p ['total_consults']=0 
                            p ['completed_consults']=0 
                            p ['pending_consults']=0 
                            p ['first_request_date']=''
                            p ['last_consult_date']=''
                    try :
                        _append_log (public_job_id ,'enriched_patients_preview: '+', '.join ([f"{p .get ('patient_name')}: {p .get ('first_request_date')or '-'} -> {p .get ('last_consult_date')or '-'}"for p in per_patient [:20 ]]))
                    except Exception :
                        pass 
                    if fmt =='csv':
                        data =_generate_csv_bytes (per_patient )
                        ext ='csv'
                    else :
                        pdf =_generate_general_pdf_bytes (per_patient ,summary )
                        if pdf is None :
                            _append_log (public_job_id ,'PDF generation not available')
                            return False 
                        data =pdf 
                        ext ='pdf'
                    base =os .path .join (os .getcwd (),'tmp_uploads')
                    os .makedirs (base ,exist_ok =True )
                    fname =f"{public_job_id }_Relatorio_Geral.{ext }"
                    path =os .path .join (base ,fname )
                    with open (path ,'wb')as fh :
                        fh .write (data )
                    _REPORT_RESULTS [public_job_id ]=fname 
                    _append_log (public_job_id ,f'written {path }')
                    return True 
                except Exception as e :
                    _append_log (public_job_id ,f'job exception: {e }')
                    return False 
                finally :
                    try :
                        if pool and created_session :
                            pool .close_session (created_session )
                            _append_log (public_job_id ,f'closed browser session {created_session }')
                    except Exception :
                        pass 
            internal =get_default_manager ().submit (_job )
            _REPORT_PUBLIC_TO_INTERNAL [public_job_id ]=internal 
            _REPORT_JOB_LOGS .setdefault (public_job_id ,[]).append (f'submitted internal job {internal }')
            return JSONResponse ({'ok':True ,'job_id':public_job_id })
        filename_base =f"Relatorio_Geral"
        if fmt =='csv':
            data =_generate_csv_bytes (per_patient )
            headers ={'Content-Disposition':f'attachment; filename="{filename_base }.csv"'}
            return Response (content =data ,media_type ='text/csv',headers =headers )
        elif fmt =='pdf':
            pdf =_generate_general_pdf_bytes (per_patient ,summary )
            if pdf is None :
                raise HTTPException (status_code =501 ,detail ='PDF generation not available (reportlab missing)')
            headers ={'Content-Disposition':f'attachment; filename="{filename_base }.pdf"'}
            return Response (content =pdf ,media_type ='application/pdf',headers =headers )
        else :
            raise HTTPException (status_code =400 ,detail ='Unsupported format')
    except HTTPException :
        raise 
    except Exception as e :
        logger .exception ('api_report_general error')
        raise HTTPException (status_code =500 ,detail =str (e ))
@router .get ('/api/reports/job/{job_id}')
async def api_report_job (request :Request ,job_id :str ):
    try :
        download =(request .query_params .get ('download')or '').lower ()in ('1','true','yes')
        logs =_REPORT_JOB_LOGS .get (job_id ,[])
        internal =_REPORT_PUBLIC_TO_INTERNAL .get (job_id )
        result_fname =_REPORT_RESULTS .get (job_id )
        if download :
            if not result_fname :
                return JSONResponse ({'ok':False ,'ready':False ,'message':'report not ready'},status_code =404 )
            path =os .path .join (os .getcwd (),'tmp_uploads',result_fname )
            if not os .path .exists (path ):
                return JSONResponse ({'ok':False ,'ready':False ,'message':'file missing'},status_code =500 )
            with open (path ,'rb')as fh :
                data =fh .read ()
            headers ={'Content-Disposition':f'attachment; filename="{result_fname }"'}
            return Response (content =data ,media_type ='application/octet-stream',headers =headers )
        status ='pending'
        if result_fname :
            status ='ready'
        elif internal :
            status ='running'
        elif not logs :
            status ='not_found'
        return JSONResponse ({'ok':True ,'job_id':job_id ,'status':status ,'logs':logs ,'filename':result_fname })
    except Exception as e :
        logger .exception ('api_report_job error')
        raise HTTPException (status_code =500 ,detail =str (e ))