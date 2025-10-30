import getpass 
from typing import Optional 
import typer 
from .client import ActivationClient ,ActivationError 
from .storage import LocalStore 
from .verify import verify_token 
from ..utils .logging import configure_logging 
import logging 
app =typer .Typer ()
logger =logging .getLogger (__name__ )
@app .command ()
def activate (base_url :str ="https://moodar-activation.squareweb.app",code :Optional [str ]=None ,master_password :Optional [str ]=None ):
    configure_logging ()
    store =LocalStore ()
    client =ActivationClient (base_url )
    if code is None :
        code =typer .prompt ("Activation code (8 digits)")
    if master_password is None :
        master_password =getpass .getpass ("Master password: ")
    try :
        typer .echo ("Confirming code...")
        client .confirm_code (code )
        typer .echo ("Submitting master password and retrieving credentials...")
        envelope =client .submit_master_key (code ,master_password )
        creds =envelope .get ("credentials",[])
        if not creds :
            typer .echo ("No credentials returned by server.")
            raise typer .Exit (code =1 )
        store .ensure_dirs ()
        for c in creds :
            name =c .get ("name")
            token =c .get ("token")
            salt =c .get ("salt")
            typer .echo (f"Saving {name }...")
            store .save_credential (name ,token ,salt )
            typer .echo (f"Verifying {name }...")
            try :
                verify_token (token ,salt ,master_password )
            except Exception as e :
                typer .echo (f"Verification failed for {name }: {e }")
                raise typer .Exit (code =2 )
        store .save_state ({"activated":True })
        typer .echo ("Activation complete. Credentials saved.")
    except ActivationError as e :
        typer .echo (f"Activation failed: {e }")
        raise typer .Exit (code =3 )