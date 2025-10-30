from pathlib import Path 
import json 
import os 
import shutil
from typing import Optional 
import warnings 
try :
    import appdirs 
    def _user_data_dir (app_name :str )->str :
        return appdirs .user_data_dir (app_name )
except Exception :
    import platform as _platform 
    def _user_data_dir (app_name :str )->str :
        warnings .warn (
        "optional dependency 'appdirs' is not installed; using a best-effort "
        "fallback for user data directory. Install 'appdirs' to silence this "
        "warning and provide a more canonical path.",
        RuntimeWarning ,
        )
        system =_platform .system ()
        home =os .path .expanduser ("~")
        if system =="Windows":
            local =os .getenv ("LOCALAPPDATA")or os .getenv ("APPDATA")
            if local :
                return os .path .join (local ,app_name )
            return os .path .join (home ,"AppData","Local",app_name )
        if system =="Darwin":
            return os .path .join (home ,"Library","Application Support",app_name )
        xdg =os .getenv ("XDG_DATA_HOME")
        if xdg :
            return os .path .join (xdg ,app_name )
        return os .path .join (home ,".local","share",app_name )
class LocalStore :
    def __init__ (self ,app_name :str ="dv_admin_automator"):
        self .app_name =app_name 
        self .base_dir =Path (_user_data_dir (app_name ))
        self .creds_dir =self .base_dir /"credenciais"
        self .state_file =self .base_dir /"state.json"
    def ensure_dirs (self ):
        self .creds_dir .mkdir (parents =True ,exist_ok =True )
        try :
            os .chmod (self .base_dir ,0o700 )
        except Exception :
            pass 
    def save_credential (self ,name :str ,token :str ,salt_b64 :Optional [str ]=None ):
        self .ensure_dirs ()
        # Clear any existing credentials in the creds_dir before saving the new one.
        # This ensures that after a new activation only the freshly received
        # credential files are present.
        try:
            for child in self.creds_dir.iterdir():
                # remove files and dirs recursively
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    try:
                        child.unlink()
                    except Exception:
                        # best-effort: ignore errors removing individual files
                        pass
        except FileNotFoundError:
            # creds_dir may not exist yet; ensure_dirs() created it above
            pass

        p = self.creds_dir / name
        p.write_text(token, encoding="utf-8")
        if salt_b64 is not None :
            (self.creds_dir / (name + ".salt")).write_text(salt_b64, encoding="utf-8")
        return p 
    def load_state (self )->dict :
        if not self .state_file .exists ():
            return {}
        try :
            return json .loads (self .state_file .read_text (encoding ="utf-8"))
        except Exception :
            return {}
    def save_state (self ,state :dict ):
        self .base_dir .mkdir (parents =True ,exist_ok =True )
        self .state_file .write_text (json .dumps (state ,indent =2 ),encoding ="utf-8")