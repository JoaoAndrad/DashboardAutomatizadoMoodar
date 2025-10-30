from typing import Any ,Dict 
import requests 
from tenacity import Retrying ,wait_exponential ,stop_after_attempt ,retry_if_exception_type 
class ActivationError (Exception ):
    pass 
class ActivationClient :
    def __init__ (self ,base_url :str ,timeout :int =10 ,max_retries :int =3 ):
        self .base_url =base_url .rstrip ("/")
        self .timeout =timeout 
        self .max_retries =max_retries 
    def _post (self ,path :str ,json_payload :dict )->Dict [str ,Any ]:
        url =f"{self .base_url }/{path .lstrip ('/')}"
        def _call ():
            return requests .post (url ,json =json_payload ,timeout =self .timeout )
        last_exc =None 
        for attempt in Retrying (stop =stop_after_attempt (self .max_retries ),wait =wait_exponential (min =1 ,max =8 ),retry =retry_if_exception_type ((requests .RequestException ,))):
            try :
                resp =_call ()
                return resp 
            except Exception as e :
                last_exc =e 
                raise 
    def confirm_code (self ,code :str )->Dict [str ,Any ]:
        url =f"{self .base_url }/confirm_code"
        try :
            resp =requests .post (url ,json ={"code":code },timeout =self .timeout )
        except requests .RequestException as e :
            raise ActivationError (f"confirm_code network error: {e }")from e 
        if resp .status_code !=200 :
            raise ActivationError (f"confirm_code failed: {resp .status_code } {resp .text }")
        try :
            return resp .json ()
        except ValueError :
            raise ActivationError ("confirm_code: invalid JSON response")
    def submit_master_key (self ,code :str ,master_password :str )->Dict [str ,Any ]:
        url =f"{self .base_url }/submit_master_key"
        try :
            resp =requests .post (url ,json ={"code":code ,"master_password":master_password },timeout =self .timeout )
        except requests .RequestException as e :
            raise ActivationError (f"submit_master_key network error: {e }")from e 
        if resp .status_code !=200 :
            try :
                j =resp .json ()
                raise ActivationError (f"submit_master_key failed: {resp .status_code } {j }")
            except ValueError :
                raise ActivationError (f"submit_master_key failed: {resp .status_code } {resp .text }")
        try :
            return resp .json ()
        except ValueError :
            raise ActivationError ("submit_master_key: invalid JSON response")