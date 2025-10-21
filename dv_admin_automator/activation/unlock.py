from typing import Dict 
from .storage import LocalStore 
from .verify import verify_token 
import os 


class UnlockError (Exception ):
    pass 


def unlock_all (store :LocalStore ,master_password :str )->Dict [str ,bytes ]:

    store .ensure_dirs ()
    results ={}
    errors ={}
    for p in sorted (store .creds_dir .iterdir ()if store .creds_dir .exists ()else []):
        if not p .is_file ():
            continue 

        if p .suffix !='.enc':
            continue 
        name =p .name 
        token =p .read_text (encoding ='utf-8')
        salt_file =store .creds_dir /(name +'.salt')
        if not salt_file .exists ():
            errors [name ]='missing salt'
            continue 
        salt_b64 =salt_file .read_text (encoding ='utf-8')
        try :
            plaintext =verify_token (token ,salt_b64 ,master_password )
            results [name ]=plaintext 
        except Exception as e :
            errors [name ]=str (e )

    if errors :

        raise UnlockError ({'errors':errors })

    return results 
