from pydantic import BaseModel ,Field 
from typing import List ,Optional ,Any 


class BrowserConfig (BaseModel ):
    name :str =Field (default ="chrome")
    headless :bool =Field (default =True )
    window :Optional [str ]=Field (default ="1920x1080")
    timeout :int =Field (default =30 )


class AuthConfig (BaseModel ):
    method :str =Field (default ="env")
    username :Optional [str ]
    password :Optional [str ]


class Step (BaseModel ):
    type :str 
    params :Optional [Any ]
    isolate :Optional [bool ]=False 


class RunConfig (BaseModel ):
    name :Optional [str ]
    base_url :str 
    auth :Optional [AuthConfig ]
    browser :BrowserConfig =BrowserConfig ()
    steps :List [Step ]=[]
