from selenium .webdriver .remote .webdriver import WebDriver 
from selenium .webdriver .support .ui import WebDriverWait 
from selenium .webdriver .support import expected_conditions as EC 
from selenium .webdriver .common .by import By 
from typing import Optional 


class BasePage :
    def __init__ (self ,driver :WebDriver ,timeout :int =15 ):
        self .driver =driver 
        self .timeout =timeout 

    def find (self ,by :By ,value :str ):
        wait =WebDriverWait (self .driver ,self .timeout )
        return wait .until (EC .presence_of_element_located ((by ,value )))

    def click (self ,by :By ,value :str ):
        el =WebDriverWait (self .driver ,self .timeout ).until (EC .element_to_be_clickable ((by ,value )))
        el .click ()

    def fill (self ,by :By ,value :str ,text :str ):
        el =self .find (by ,value )
        el .clear ()
        el .send_keys (text )
