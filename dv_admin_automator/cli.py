from typing import Optional 
import typer 

from .config .loader import load_config 
from .executor .runner import Runner 
from .activation .cli import app as activation_app 
from .ui .web .server import serve_in_thread 

app =typer .Typer ()


app .add_typer (activation_app ,name ="activate")


@app .command ()
def ui (open_browser :bool =True ):

    url ,thread =serve_in_thread (open_browser )
    typer .echo (f"UI running at {url }")



@app .command ()
def run (config :str ,headless :Optional [bool ]=True ):

    cfg =load_config (config )
    runner =Runner (cfg ,headless =headless )
    result =runner .run ()
    if result .success :
        typer .echo ("Run completed successfully")
    else :
        typer .echo ("Run failed. Check artifacts for details")


def main ():
    app ()


if __name__ =="__main__":
    main ()
