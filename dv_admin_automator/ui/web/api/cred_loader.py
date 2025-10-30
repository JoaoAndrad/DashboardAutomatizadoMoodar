from pathlib import Path 
import os 
import json 
from typing import Optional ,Dict ,Any 
def _find_creds_dir ()->Path :
    env_override =os .environ .get ('DV_CRED_DIR')
    if env_override :
        p =Path (env_override )
        if p .exists ():
            return p 
    try :
        from dv_admin_automator .activation .storage import LocalStore 
        ls =LocalStore ()
        if ls and getattr (ls ,'creds_dir',None )and ls .creds_dir .exists ():
            return ls .creds_dir 
    except Exception :
        pass 
    root =Path (__file__ ).resolve ().parent .parent .parent .parent 
    local =root /'credenciais'
    return local 
def try_auto_load_service_account_from_local (master_password :Optional [str ]=None )->Optional [Dict [str ,Any ]]:
    mp =master_password or os .environ .get ('DV_MASTER_PASSWORD')
    if not mp :
        return None 
    creds_dir =_find_creds_dir ()
    if not creds_dir .exists ():
        return None 
    try :
        from dv_admin_automator .activation .verify import verify_token 
    except Exception :
        return None 
    for p in sorted (creds_dir .iterdir ()):
        if not p .is_file ()or not p .name .endswith ('.enc'):
            continue 
        try :
            token =p .read_text (encoding ='utf-8')
            salt_path =creds_dir /(p .name +'.salt')
            if not salt_path .exists ():
                continue 
            salt_b64 =salt_path .read_text (encoding ='utf-8')
            plaintext =verify_token (token ,salt_b64 ,mp )
            try :
                obj =json .loads (plaintext .decode ('utf-8'))
            except Exception :
                continue 
            if isinstance (obj ,dict )and ('client_email'in obj and 'private_key'in obj ):
                return obj 
        except Exception :
            continue 
    return None 