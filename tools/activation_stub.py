from fastapi import FastAPI ,HTTPException 
from pydantic import BaseModel 
import uvicorn 
import base64 
import os 
import json 
from cryptography .hazmat .primitives .kdf .pbkdf2 import PBKDF2HMAC 
from cryptography .hazmat .primitives import hashes 
from cryptography .hazmat .backends import default_backend 
from cryptography .fernet import Fernet 
import secrets 

app =FastAPI ()


REQUESTS ={}

def _approve_later (request_id :int ,delay :float =5.0 ):
    import time 
    code =str (secrets .randbelow (90000000 )+10000000 )
    time .sleep (delay )
    REQUESTS [request_id ]['status']='approved'
    REQUESTS [request_id ]['code']=code 


class RequestActivation (BaseModel ):
    device_info :dict |None =None 
    contact :str |None =None 
    metadata :dict |None =None 


class ConfirmCode (BaseModel ):
    code :str 


class SubmitMasterKey (BaseModel ):
    code :str 
    master_password :str 


@app .post ('/request_activation')
async def request_activation (payload :RequestActivation ):
    rid =secrets .randbelow (9999999 )
    REQUESTS [rid ]={'status':'pending','payload':payload .dict (),'created_at':None }

    import threading 
    t =threading .Thread (target =_approve_later ,args =(rid ,5.0 ),daemon =True )
    t .start ()
    return {'request_id':rid ,'message':'request created','payload':payload .dict ()}


@app .post ('/confirm_code')
async def confirm_code (payload :ConfirmCode ):
    code =payload .code 
    if not code or not code .isdigit ():
        raise HTTPException (status_code =400 ,detail ='invalid code')
    return {'ok':True ,'message':'code valid'}


@app .get ('/request_status/{request_id}')
async def request_status (request_id :int ):
    info =REQUESTS .get (request_id )
    if not info :
        raise HTTPException (status_code =404 ,detail ='not found')
    return {'request_id':request_id ,'status':info .get ('status','pending'),'code':info .get ('code')}


@app .post ('/submit_master_key')
async def submit_master_key (payload :SubmitMasterKey ):

    mpw =payload .master_password 
    creds =[]
    for i in range (2 ):
        name =f'dummy_cred_{i +1 }.json.enc'
        plaintext =json .dumps ({'hello':'world','idx':i }).encode ('utf-8')
        salt =secrets .token_bytes (32 )
        kdf =PBKDF2HMAC (algorithm =hashes .SHA256 (),length =32 ,salt =salt ,iterations =600000 ,backend =default_backend ())
        key =base64 .urlsafe_b64encode (kdf .derive (mpw .encode ()))
        f =Fernet (key )
        token =f .encrypt (plaintext ).decode ('utf-8')
        creds .append ({'name':name ,'token':token ,'token_format':'fernet','salt':base64 .b64encode (salt ).decode ('utf-8')})

    envelope ={'version':'1','generated_at':None ,'credentials':creds }
    return envelope 


def run (port :int =8001 ):
    uvicorn .run (app ,host ='127.0.0.1',port =port ,log_level ='info')


if __name__ =='__main__':
    run ()
