from typing import Optional 
from selenium import webdriver 
from selenium .webdriver .chrome .options import Options 
import chromedriver_autoinstaller 
import logging 
logger =logging .getLogger (__name__ )
class BrowserManager :
    def __init__ (self ,browser :str ="chrome",headless :bool =True ,window :str ="1920x1080"):
        self .browser =browser 
        self .headless =headless 
        self .window =window 
        self .driver :Optional [webdriver .Chrome ]=None 
    def start (self ):
        try :
            chromedriver_autoinstaller .install ()
        except Exception as e :
            logger .warning (
            "chromedriver_autoinstaller.install() failed: %s - retrying with no_ssl=True",
            e ,
            )
            try :
                chromedriver_autoinstaller .install (no_ssl =True )
            except Exception :
                logger .exception (
                "chromedriver_autoinstaller failed even with no_ssl=True. "
                "Consider manually installing chromedriver and placing it on PATH, "
                "or fixing system CA certificates (install certifi or run OS cert update)."
                )
                raise 
        opts =Options ()
        if self .headless :
            opts .add_argument ("--headless=new")
        opts .add_argument ("--no-sandbox")
        opts .add_argument ("--disable-dev-shm-usage")
        opts .add_argument (f"--window-size={self .window }")
        opts .add_argument ("--disable-gpu")
        opts .add_experimental_option ("excludeSwitches",["enable-automation"])
        opts .add_experimental_option ("useAutomationExtension",False )
        self .driver =webdriver .Chrome (options =opts )
        self .driver .implicitly_wait (0 )
        logger .info ("Browser started")
        return self .driver 
    def quit (self ):
        if self .driver :
            try :
                self .driver .quit ()
            except Exception :
                logger .exception ("Error quitting driver")
            finally :
                self .driver =None 