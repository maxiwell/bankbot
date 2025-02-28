import os
import re
import sys
import string
import random
from enum import Enum
from pathvalidate import sanitize_filename
from datetime import datetime

import traceback
import chardet

from playwright.sync_api import sync_playwright
from pathlib import Path

from log import Log

class Status (Enum):
    OK              = 0
    ERROR           = 1
    BANK_NOT_FOUND  = 2

    def getText(self, msg = ""):
        if self == Status.OK:
            return "OK"
        elif self == Status.ERROR:
            return "ERROR"
        elif self == Status.BANK_NOT_FOUND:
            return f"Banco não encontrado: {msg}"

class BankBot:

    def __init__(self, headless = False, debug = False,
                 workspace = str(Path.home()) + "/bankbot"):
        self.headless  = headless
        self.workspace = workspace
        self.pause_if_error = False
        self.debug = debug
        self.logfile = workspace + "/bankbot.log"

        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'

    def get_filename_content(self, filename):
        with open(filename, "rb") as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding_detected = result["encoding"]

        with open(filename, "r", encoding=encoding_detected, errors="replace") as f:
            ofx_string = f.read()

        return ofx_string

    def save_file_from_page(self, download_info, filename):
        # Wait for the download process to complete and save the downloaded file somewhere
        download = download_info.value
        download.save_as(filename)

        return self.get_filename_content(filename)

    def save_file_from_request(self, response, file):
        with open(file, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

    def init(self):
        # The bank must to set the 'self.base_url' and 'self.bank_name'
        raise NotImplementedError

    def init_caller(self):
        self.init()

        # generate the unique tag to this thread
        self.tag = self.get_tag()
        Path(self.workspace).mkdir(parents=True, exist_ok=True)

        self.ofx_dir        = os.path.join(self.workspace)
        self.screenshot_dir = os.path.join(self.workspace)

        self.__log = Log(self.tag, self.logfile)

        return self

    def get_context(self):
        headers = {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "sec-ch-ua": '"Not(A:Brand";v="99", "Chromium";v="133")'
        }

        context = self.browser.new_context(
            user_agent=self.user_agent,
            extra_http_headers=headers
        )

        return context

    def __build_browser(self, pw):

        self.browser = pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-popup-blocking",
                "--safebrowsing-disable-download-protection",
                "--deny-permission-prompts"
            ],
            slow_mo=220
        )

        self.context = self.get_context()
        self.page = self.context.new_page()

        def log_request(request):
            print(f"URL: {request.url}")
            print(f"Method: {request.method}")
            if request.post_data:
                print(f"POST Data: {request.post_data}")
            print(f"Headers: {request.headers}")
            print("-" * 80)

        if self.debug:
            self.page.on("request", log_request)

        # Set the default timeout for all operations
        self.page.set_default_timeout(20000)

        return self.page

    def get_tag(self):
        if not hasattr(self, 'tag') or self.tag is None:
            characters = string.ascii_letters + string.digits
            unique = ''.join(random.choices(characters, k=6)).lower()

            self.tag = self.bank_name + "_" + unique

            self.tag = self.tag.replace("/", "_")
            self.tag = self.tag.replace(" ", "_")
            self.tag = sanitize_filename(self.tag)

        return self.tag

    def log(self, message):
        self.__log.info(message)

    def create_filename(self, pos= "", pre= ""):
        dt = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = self.get_tag()
        name = pre + f"{tag}_{dt}" + pos
        name = name.replace('/', '_')
        name = re.sub(r'\s+', '', name)
        return name

    def json_return(self, status: Status, message: str, ofx: str = None):
        png = None
        srv = ""
        tag = self.get_tag()

        if status != Status.OK:
            self.log(traceback.format_exc())
            try:
                png = self.screenshot_dir + "/" + self.create_filename("_ss.png")
                self.page.screenshot(path=f"{png}")
            except Exception as e:
                png = None
                self.log(f"Failed to save screenshot: {e}")

        ret = {
            "ofx": ofx,
            "cod": status.value,
            "message": message,
            "png": png,
            "srv": srv,
            "tag": tag
        }

        return ret


    # @param page: Playwright page object
    # @param data: Dictionary with bank parameters
    def run(self, page, data):
        # The bank must to implement this method
        raise NotImplementedError

    def run_caller(self, data):
        response_json = ""
        with sync_playwright() as pw:
            ts_begin = datetime.now().timestamp()
            try:
                page = self.__build_browser(pw)

                # Call the bank run method
                response_json = self.run(page, data)

            except Exception as e:
                response_json = self.json_return(Status.ERROR, str(e))
                if self.pause_if_error:
                    page.pause()

            return response_json


    def start(self, data):
        return self.init_caller().run_caller(data)


if __name__ == "__main__":

    # -------------------------------------------------------
    # You can call this file directly to test some
    # function, like the example below
    # -------------------------------------------------------

    test_bankbot = BankBot();
    file = "teste.ofx"
    ofx = test_bankbot._BankBot__get_filename_content(file)
    print(ofx)
