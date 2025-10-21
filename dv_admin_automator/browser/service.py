import logging 
from typing import Optional 

from .manager import BrowserManager 

logger =logging .getLogger ("dv_admin_automator.browser.service")


class BrowserService :


    def __init__ (self ,browser :str ="chrome",headless :bool =False ,window :str ="1920x1080"):
        self .browser =browser 
        self .headless =headless 
        self .window =window 

    def login_to_site (self ,url :str ,username :str ,password :str ,timeout :int =10 )->None :

        logger .info ('login_to_site: starting browser (headless=%s)',self .headless )
        bm =BrowserManager (headless =self .headless ,window =self .window )
        driver =bm .start ()
        try :
            from selenium .webdriver .common .by import By 
            from selenium .webdriver .support .ui import WebDriverWait 
            from selenium .webdriver .support import expected_conditions as EC 
            import time 

            wait =WebDriverWait (driver ,timeout )
            logger .info ('Navigating to %s',url )
            driver .get (url )
            time .sleep (1 )

            username_selector ="input[type='text'], input[name='username'], input[name='user'], input[id*='username'], input[id*='user'], input[placeholder*='usuário'], input[placeholder*='username']"
            password_selector ="input[type='password'], input[name='password'], input[id*='password'], input[placeholder*='senha']"

            u_field =wait .until (EC .presence_of_element_located ((By .CSS_SELECTOR ,username_selector )))
            p_field =driver .find_element (By .CSS_SELECTOR ,password_selector )

            u_field .clear ();u_field .send_keys (username )
            p_field .clear ();p_field .send_keys (password )


            try :
                login_btn =driver .find_element (By .CSS_SELECTOR ,"button[type='submit'], input[type='submit'], button[class*='login'], button[class*='entrar']")
                login_btn .click ()
            except Exception :
                logger .exception ('Login button not found or click failed')

            time .sleep (3 )
            logger .info ('login_to_site finished, leaving browser open for inspection')
        finally :


            pass 
