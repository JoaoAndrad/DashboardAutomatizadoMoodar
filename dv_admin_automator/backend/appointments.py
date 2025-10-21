from datetime import datetime ,timedelta 
from typing import Dict ,Any 

def schedule_cycle_appointments (
participant_id :str ,
participant_name :str =None ,
therapist :str =None ,
plan :str =None ,
start_date :str =None ,
start_time :str =None ,
tipo :str =None ,
minutagem :str =None ,
quantidade :int =None ,
manager =None ,
headless :bool =True 
)->Dict [str ,Any ]:

    pool =get_default_pool ()
    created =None 
    print ("[schedule_cycle_appointments] INICIANDO AGENDAMENTO DE CICLO")
    print (f"  participant_id={participant_id } therapist={therapist } plan={plan } start_date={start_date } start_time={start_time } tipo={tipo } minutagem={minutagem } quantidade={quantidade }")
    try :
        if manager is not None :
            mgr =manager 
            driver =getattr (mgr ,'driver',None )
            print (f"  [sessão pool] Usando manager EXISTENTE (mesmo navegador da busca): {mgr }")
            created =None 
        else :
            created =pool .create_session (headless =headless )
            mgr =pool .get_manager (created )
            driver =getattr (mgr ,'driver',None )if mgr else None 
            print (f"  [sessão pool] Criada nova sessão: {created } manager={mgr }")
        if not driver :
            print ("  [ERRO] Nenhum driver Selenium disponível!")
            return {'ok':False ,'error':'no_driver'}
        try :
            print (f"  [DEBUG] Current URL before scheduling: {driver .current_url }")
        except Exception as e :
            print (f"  [DEBUG] Could not get current_url: {e }")

        interval_days =14 if tipo .lower ().startswith ('quinzenal')else 7 
        try :
            qtd =int (quantidade )
        except Exception :
            qtd =3 if interval_days ==14 else 5 
        print (f"  [datas] Intervalo: {interval_days } dias | Quantidade: {qtd }")

        dt0 =datetime .strptime (f"{start_date } {start_time }","%Y-%m-%d %H:%M")
        datas =[dt0 +timedelta (days =interval_days *i )for i in range (qtd )]
        print (f"  [datas] Datas calculadas: {[d .strftime ('%Y-%m-%d %H:%M')for d in datas ]}")

        def criar_appointment (data ):
            try :
                print (f"    [criar] Iniciando criação para {data .strftime ('%Y-%m-%d %H:%M')}")
                driver .get (f'https://webapp.moodar.com.br/moodashboard/appointment_app/appointment/add/')
                time .sleep (2 )

                patient_select2 =driver .find_element ('css selector','.field-patient .select2-selection')
                patient_select2 .click ()
                time .sleep (0.5 )
                search_input =driver .find_element ('css selector','.select2-search__field')
                search_input .clear ()
                search_input .send_keys (str (participant_id ))
                time .sleep (1.5 )

                selected_patient =False 
                try :
                    results =driver .find_elements ('css selector','.select2-results__option')
                except Exception :
                    results =[]


                for result in results :
                    try :
                        txt =result .text .strip ()
                        if not txt :
                            continue 

                        import re as _re 
                        m =_re .match (r'^(\d+)[\s\-:]+',txt )
                        if m and m .group (1 )==str (participant_id ):
                            result .click ()
                            selected_patient =True 
                            break 
                        if txt .startswith (str (participant_id )):
                            result .click ()
                            selected_patient =True 
                            break 
                    except Exception :
                        continue 


                if not selected_patient and participant_name :

                    if not results :
                        try :
                            search_input .clear ()
                            search_input .send_keys (str (participant_name ))
                            time .sleep (1.5 )
                            results =driver .find_elements ('css selector','.select2-results__option')
                        except Exception :
                            results =[]

                    for result in results :
                        try :
                            txt =result .text .strip ()
                            if not txt :
                                continue 
                            if participant_name .lower ()in txt .lower ():
                                try :
                                    result .click ()
                                except Exception :
                                    try :
                                        driver .execute_script ("arguments[0].click();",result )
                                    except Exception :
                                        continue 
                                selected_patient =True 
                                break 
                        except Exception :
                            continue 

                if not selected_patient :
                    print (f"      [criar] Falha ao selecionar paciente ID {participant_id } (nome='{participant_name }')")
                    raise Exception ("Paciente não selecionado")
                print (f"      [criar] Paciente selecionado")


                try :
                    driver .find_element ('css selector','body').click ()
                    time .sleep (0.2 )
                except Exception :
                    pass 

                therapist_select2 =driver .find_element ('css selector','.field-therapist .select2-selection')

                try :
                    therapist_select2 .click ()
                except Exception :
                    try :
                        driver .execute_script ("arguments[0].click();",therapist_select2 )
                    except Exception :
                        pass 
                time .sleep (0.5 )

                search_input =driver .find_element ('css selector','.select2-search__field')
                search_input .clear ()
                search_input .send_keys (therapist )
                time .sleep (1.0 )


                try :
                    results =driver .find_elements ('css selector','.select2-results__option')
                except Exception :
                    results =[]

                selected =False 
                for r in results :
                    try :
                        text =r .text .strip ()
                        if text and therapist .lower ()in text .lower ():
                            try :
                                r .click ()
                                selected =True 
                                break 
                            except Exception :
                                try :
                                    driver .execute_script ("arguments[0].click();",r )
                                    selected =True 
                                    break 
                                except Exception :
                                    continue 
                    except Exception :
                        continue 


                if not selected and results :
                    try :
                        results [0 ].click ()
                        selected =True 
                    except Exception :
                        try :
                            driver .execute_script ("arguments[0].click();",results [0 ])
                            selected =True 
                        except Exception :
                            selected =False 

                if not selected :
                    print (f"      [criar] Falha ao selecionar terapeuta: nenhum resultado clicável encontrado para '{therapist }'")
                else :
                    print (f"      [criar] Terapeuta selecionado")

                driver .find_element ('id','id_schedule_0').send_keys (data .strftime ('%Y-%m-%d'))
                driver .find_element ('id','id_schedule_1').send_keys (data .strftime ('%H:%M'))

                from selenium .webdriver .support .select import Select 
                Select (driver .find_element ('id','id_duration')).select_by_visible_text (f"{minutagem } minutos"if 'min'not in minutagem else minutagem )

                status ='Remarcada'
                Select (driver .find_element ('id','id_status')).select_by_visible_text (status )

                driver .find_element ('id','id_associated_plan').send_keys (plan )

                driver .find_element ('name','_continue').click ()
                time .sleep (2 )

                Select (driver .find_element ('id','id_status')).select_by_visible_text ('Confirmada')
                driver .find_element ('name','_save').click ()
                time .sleep (1 )
                print (f"    [criar] Consulta criada e confirmada!")
                return {'ok':True ,'date':data .strftime ('%Y-%m-%d %H:%M')}
            except Exception as e :
                print (f"    [ERRO criar] Falha ao criar consulta: {e }")
                return {'ok':False ,'date':data .strftime ('%Y-%m-%d %H:%M'),'error':str (e )}

        resultados =[]
        for data in datas :
            resultados .append (criar_appointment (data ))

        print (f"[schedule_cycle_appointments] FINALIZADO. Criadas: {len ([r for r in resultados if r ['ok']])} | Falhas: {len ([r for r in resultados if not r ['ok']])}")
        return {
        'ok':True ,
        'created':[r for r in resultados if r ['ok']],
        'failed':[r for r in resultados if not r ['ok']],
        'total':len (resultados )
        }
    finally :
        try :
            if created :
                print (f"[schedule_cycle_appointments] Encerrando sessão criada: {created }")
                pool .close_session (created )
        except Exception as e :
            print (f"[schedule_cycle_appointments] Erro ao fechar sessão: {e }")
"""Minimal participant search helper for appointments feature.

Provides a single function `search_participant_rows(query, manager=None, headless=True)`
that returns a list of participant dicts compatible with the legacy code.
"""
import time 
import re 
from typing import List ,Dict ,Any ,Optional 

from dv_admin_automator .browser .pool import get_default_pool 


def _safe_text (el ):
    try :
        return el .text .strip ()
    except Exception :
        return ''


def search_participant_rows (query :str ,manager =None ,headless :bool =True )->List [Dict [str ,Any ]]:

    pool =get_default_pool ()
    created =None 
    results :List [Dict [str ,Any ]]=[]

    try :
        if manager is not None :
            mgr =manager 
            driver =getattr (mgr ,'driver',None )
        else :
            created =pool .create_session (headless =headless )
            mgr =pool .get_manager (created )
            driver =getattr (mgr ,'driver',None )if mgr else None 

        if not driver :
            return []

        url ='https://webapp.moodar.com.br/moodashboard/app_eleve/participante/'
        driver .get (url )
        time .sleep (1.2 )

        normalized =re .sub (r'[^\d]','',str (query ))

        def _submit (qv :str ):
            try :
                sb =driver .find_element ('id','searchbar')
                sb .clear ()
                sb .send_keys (str (qv ))
                sb .submit ()
                time .sleep (1.5 )
                return True 
            except Exception :
                return False 

        _submit (query )
        try :
            rows =driver .find_elements ('css selector','#result_list tbody tr')
        except Exception :
            rows =[]

        if not rows and normalized !=str (query ):
            _submit (normalized )
            try :
                rows =driver .find_elements ('css selector','#result_list tbody tr')
            except Exception :
                rows =[]

        if not rows :
            return []

        for row in rows :
            try :
                link =row .find_element ('css selector','th.field-nome a')
                urlp =link .get_attribute ('href')or ''
                name =_safe_text (link )
                pid =urlp .split ('/participante/')[1 ].split ('/')[0 ]if '/participante/'in urlp else ''
            except Exception :
                urlp =''
                name =''
                pid =''

            try :
                email =row .find_element ('css selector','td.field-email').text .strip ()
            except Exception :
                email ='-'
            try :
                phone =row .find_element ('css selector','td.field-telefone').text .strip ()
            except Exception :
                phone ='-'
            try :
                cpf =row .find_element ('css selector','td.field-cpf').text .strip ()
            except Exception :
                cpf ='-'
            try :
                status =row .find_element ('css selector','td.field-status').text .strip ()
            except Exception :
                status ='-'
            try :
                created_at =row .find_element ('css selector','td.field-created_at').text .strip ()
            except Exception :
                created_at ='-'
            try :
                updated_at =row .find_element ('css selector','td.field-updated_at').text .strip ()
            except Exception :
                updated_at ='-'
            try :
                uid =row .find_element ('css selector','td.field-uid').text .strip ()
            except Exception :
                uid ='-'

            results .append ({
            'id':pid ,
            'name':name ,
            'email':email ,
            'phone':phone ,
            'cpf':cpf ,
            'status':status ,
            'created_at':created_at ,
            'updated_at':updated_at ,
            'uid':uid ,
            'url':urlp 
            })

        return results 

    finally :
        try :
            if created :
                pool .close_session (created )
        except Exception :
            pass 


def get_participant_history (participant_id :str ,manager =None ,headless :bool =True )->dict :

    import time 
    pool =get_default_pool ()
    created =None 
    try :
        if manager is not None :
            mgr =manager 
            driver =getattr (mgr ,'driver',None )
        else :
            created =pool .create_session (headless =headless )
            mgr =pool .get_manager (created )
            driver =getattr (mgr ,'driver',None )if mgr else None 

        if not driver :
            return {}

        url =f'https://webapp.moodar.com.br/moodashboard/appointment_app/appointment/?q={participant_id }'
        driver .get (url )
        time .sleep (2 )
        try :
            print (f"  [history] current_url={driver .current_url }")
        except Exception :
            pass 


        try :
            search_box =driver .find_element ('id','searchbar')
            search_box .clear ()
            search_box .send_keys (str (participant_id ))
            search_box .submit ()
            time .sleep (2 )
        except Exception :
            return {}


        try :
            rows =driver .find_elements ('css selector','#result_list tbody tr')
            print (f"  [history] found {len (rows )} rows in #result_list")
        except Exception as e :
            print (f"  [history] error finding rows: {e }")
            rows =[]

        if not rows :
            return {}

        appointments =[]
        for idx ,row in enumerate (rows [:20 ]):
            try :
                try :
                    raw =row .get_attribute ('innerText')
                except Exception :
                    raw ='[no innerText]'
                print (f"  [history][row {idx }] raw=\n{raw }")
                cells =row .find_elements ('tag name','td')
                cell_texts =[]
                for ci ,c in enumerate (cells ):
                    try :
                        txt =c .text .strip ()
                    except Exception :
                        txt =''
                    cell_texts .append (txt )
                    print (f"    [history][row {idx }][cell {ci }] '{txt }'")

                if len (cells )>=7 :
                    appointment ={
                    'patient':cell_texts [0 ],
                    'therapist':cell_texts [1 ],
                    'schedule':cell_texts [2 ],
                    'duration':cell_texts [3 ],
                    'status':cell_texts [4 ],
                    'plan':cell_texts [5 ],
                    'device':cell_texts [6 ]if len (cell_texts )>6 else '',
                    'id':cell_texts [7 ]if len (cell_texts )>7 else ''
                    }
                    appointments .append (appointment )
                else :
                    print (f"    [history][row {idx }] skipped: not enough cells ({len (cells )})")
            except Exception as e :
                print (f"    [history][row {idx }] parse error: {e }")
                continue 

        if not appointments :
            return {}



        from collections import Counter ,defaultdict 
        cycle_counter =Counter ()
        cycle_examples ={}
        for appt in appointments :
            key =(appt .get ('plan',''),appt .get ('therapist',''))
            cycle_counter [key ]+=1 
            if key not in cycle_examples :
                cycle_examples [key ]=appt 

        print (f"  [history] parsed {len (appointments )} appointments; cycles found: {len (cycle_counter )}")

        cycles =[]
        for (plan ,therapist ),count in cycle_counter .items ():
            example =cycle_examples [(plan ,therapist )]
            cycles .append ({
            'name':example ['patient'],
            'plan':plan ,
            'therapist':therapist ,
            'matches':count 
            })

        history ={
        'participant_id':participant_id ,
        'total_appointments':len (appointments ),
        'appointments':appointments ,
        'cycles':cycles ,
        'has_previous_cycles':len (appointments )>0 
        }

        return history 

    finally :
        try :
            if created :
                pool .close_session (created )
        except Exception :
            pass 
