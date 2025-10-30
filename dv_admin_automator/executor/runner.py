from dataclasses import dataclass 
from typing import Any 
from ..config .schema import RunConfig 
from ..browser .manager import BrowserManager 
import time 
import logging 
from ..activation .storage import LocalStore 
from ..activation .unlock import unlock_all ,UnlockError 
import getpass 
logger =logging .getLogger (__name__ )
@dataclass 
class RunResult :
    success :bool 
    details :Any =None 
class Runner :
    def __init__ (self ,config :RunConfig ,headless :bool =True ):
        self .config =config 
        self .config .browser .headless =headless 
        self .browser_manager =BrowserManager (headless =self .config .browser .headless ,window =self .config .browser .window )
        self .decrypted_creds ={}
    def run (self )->RunResult :
        driver =None 
        try :
            store =LocalStore ()
            state =store .load_state ()
            decrypted_creds =None 
            if state .get ('activated'):
                import os 
                try_count =0 
                max_attempts =int (os .environ .get ('DV_MAX_UNLOCK_ATTEMPTS','3'))
                last_error =None 
                while try_count <max_attempts :
                    mpw =getpass .getpass ('Master password to unlock credentials: ')
                    try :
                        decrypted_creds =unlock_all (store ,mpw )
                        self .decrypted_creds =decrypted_creds 
                        logging .getLogger (__name__ ).info ('Credentials unlocked in-memory')
                        last_error =None 
                        break 
                    except UnlockError as e :
                        last_error =e 
                        try_count +=1 
                        logging .getLogger (__name__ ).warning (f'Unlock attempt {try_count } failed')
                        if try_count <max_attempts :
                            print (f'Unlock failed. You have {max_attempts -try_count } attempts left.')
                if last_error is not None :
                    logging .getLogger (__name__ ).error (f'Failed to unlock credentials after {max_attempts } attempts: {last_error }')
                    return RunResult (success =False ,details ={'error':'unlock_failed','reason':str (last_error )})
            driver =self .browser_manager .start ()
            base =self .config .base_url 
            logger .info (f"Navigating to {base }")
            driver .get (base )
            for step in self .config .steps :
                logger .info (f"Executing step {step .type } with params {step .params }")
                time .sleep (0.5 )
            return RunResult (success =True ,details ={"steps":len (self .config .steps )})
        except Exception :
            logger .exception ("Run failed")
            return RunResult (success =False )
        finally :
            if self .browser_manager :
                self .browser_manager .quit ()