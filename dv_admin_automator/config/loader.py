import json 
from pathlib import Path 
from typing import Any 
import yaml 
from .schema import RunConfig 
def load_config (path :str )->RunConfig :
    p =Path (path )
    if not p .exists ():
        raise FileNotFoundError (f"Config file not found: {path }")
    text =p .read_text (encoding ="utf-8")
    data :Any 
    if p .suffix in (".yml",".yaml"):
        data =yaml .safe_load (text )
    elif p .suffix ==".json":
        data =json .loads (text )
    else :
        data =yaml .safe_load (text )
    cfg =RunConfig (**(data or {}))
    return cfg 