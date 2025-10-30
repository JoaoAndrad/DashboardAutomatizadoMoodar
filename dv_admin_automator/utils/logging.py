from loguru import logger 
from rich .logging import RichHandler 
import sys 
def configure_logging (level :str ="INFO"):
    logger .remove ()
    logger .add (sys .stderr ,level =level ,colorize =True ,format ="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
    import logging as stdlib_logging 
    handler =RichHandler (rich_tracebacks =True )
    stdlib_logging .basicConfig (level =level ,handlers =[handler ])