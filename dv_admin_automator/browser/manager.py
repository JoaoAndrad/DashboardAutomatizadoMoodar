from typing import Optional
import os
import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller


logger =logging .getLogger (__name__ )


class BrowserManager :
    def __init__ (self ,browser :str ="chrome",headless :bool =True ,window :str ="1920x1080"):
        self .browser =browser 
        self .headless =headless 
        self .window =window 
        self .driver :Optional [webdriver .Chrome ]=None 

    def start (self ):
        """Start a Chrome webdriver.

        Behavior:
        - If SELENIUM_REMOTE_URL environment variable is set, connect to that Remote WebDriver (recommended for Docker Compose).
        - Otherwise try to install a local chromedriver with chromedriver_autoinstaller and start a local Chrome.
        """

        opts = Options()
        if self.headless:
            # new headless flag
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument(f"--window-size={self.window}")
        opts.add_argument("--disable-gpu")

        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        remote_url = os.environ.get("SELENIUM_REMOTE_URL")
        try:
            if remote_url:
                logger.info("Connecting to remote Selenium at %s", remote_url)
                # Selenium 4: can pass options to Remote
                self.driver = webdriver.Remote(command_executor=remote_url, options=opts)
            else:
                # attempt to install a matching chromedriver and start a local Chrome
                chromedriver_autoinstaller.install()
                self.driver = webdriver.Chrome(options=opts)

            # don't wait implicitly by default (tests/jobs manage waits explicitly)
            if self.driver:
                self.driver.implicitly_wait(0)
                logger.info("Browser started (headless=%s) via %s", self.headless, 'remote' if remote_url else 'local')
            return self.driver
        except Exception:
            logger.exception("Failed to start browser")
            raise

    def quit (self ):
        if self .driver :
            try :
                self .driver .quit ()
            except Exception :
                logger .exception ("Error quitting driver")
            finally :
                self .driver =None 
