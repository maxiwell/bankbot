import requests
import time
import random
import re
import sys
from datetime import datetime
import json
import click

from bankbot import *

class Itau(BankBot):

    def init(self):
        self.base_url  = 'https://www.itau.com.br'
        #self.base_url  = "https://google.com"
        self.bank_name = 'Itau'


    def __get_number_keys(self, page) -> dict:

        page.wait_for_selector('.teclas.clearfix a')
        links = page.query_selector_all('.teclas.clearfix a')
        keys = {}
        for link in links:
            numbers = link.get_attribute('aria-label')
            # parse numbers from aria-label in the format "1 ou 3" and "2 ou 4"
            keys[numbers.split(' ')[0]] = link
            keys[numbers.split(' ')[2]] = link
        return keys

    def __enter_password(self, page, senha):
        keys = self.__get_number_keys(page)

        for digit in senha:
            keys[digit].click()
            page.wait_for_timeout(1000)

        page.click('#acessar')

    def __login(self, page, agencia, conta, senha):
        page.goto(self.base_url)

        page.click('button#open_modal_more_access')
        page.wait_for_selector('div.idl-modal-more-access-container')

        page.click('input#idl-more-access-input-agency')

        print("typing agency")
        page.type('input#idl-more-access-input-agency', agencia, delay=50)

        page.click('input#idl-more-access-input-account')

        print("typing account")
        page.type('input#idl-more-access-input-account', conta, delay=50)

        time.sleep(random.randint(1,3))

        # accept cookies
        if page.locator("button#itau-cookie-consent-banner-accept-cookies-btn").is_visible():
            page.click("button#itau-cookie-consent-banner-accept-cookies-btn")

        page.wait_for_selector('button#idl-more-access-submit-button:not([disabled])')
        page.click('button#idl-more-access-submit-button')
        page.wait_for_load_state('networkidle')

        print("typing password")
        self.__enter_password(page, senha)


    def __extrato(self, page):
        show_button = '#saldo-extrato-card-accordion'
        ver_extrato = 'button[aria-label="ver extrato"]'

        time.sleep(random.randint(3,5))

        if not page.is_visible(ver_extrato):
            page.wait_for_selector(show_button)
            page.click(show_button)

        page.wait_for_load_state('domcontentloaded')
        page.wait_for_selector(ver_extrato)

        page.click(ver_extrato)
        page.wait_for_load_state('domcontentloaded')

        statement_select = 'div#periodoFiltro'
        statement_days = "90"

        page.click(statement_select)  # Replace with the selector for the expandable div

        page.wait_for_selector("ul#periodoFiltroList")
        # Scroll to the last item in the list to ensure all options are loaded
        list_items = page.locator("ul#periodoFiltroList li")  # Select all list items; adjust the selector if necessary

        # Scroll until you find the specific 'li' with `data-id="90"`
        for i in range(list_items.count()):
            item = list_items.nth(i)
            item.scroll_into_view_if_needed()

            # Check if the item has `data-id="90"`
            if item.get_attribute("data-id") == statement_days:
                item.click()
                break

        page.wait_for_load_state('networkidle')


    def __get_ofx(self, page):
        page.get_by_role("button", name="salvar como").click()

        # Start waiting for the download
        with page.expect_download() as download_info:

            # Perform the action that initiates download
            page.get_by_role("button", name="salvar em OFX").click()

            filename = self.ofx_dir + "/" + self.create_filename(".ofx")
            return self.save_file_from_page(download_info, filename)


    def __get_credit_card(self, page):
        time.sleep(random.randint(3,5))
        page.get_by_role("link", name=" menu").hover()
        page.get_by_role("link", name="cartões").click()

        time.sleep(random.randint(1,3))
        page.locator("#detalharCartao1").click()

        time.sleep(random.randint(1,3))
        page.locator("#conteudo1").get_by_role("link", name="ver fatura").click()

        time.sleep(random.randint(4,7))

        # Mes Atual
        page.locator("#botao-opcoes-lancamentos").click()
        with page.expect_download() as download_info:

            page.get_by_role("button", name="salvar em Excel").first.click()

            filename = self.ofx_dir + "/" + self.create_filename("_mar.xlsx")
            self.save_file_from_page(download_info, filename)

        # Mes Anterior
        page.get_by_role("tab", name="fevereiro: Fatura fechada R$").click()
        page.locator("#botao-opcoes-lancamentos").click()

        with page.expect_download() as download_info:
            page.get_by_role("button", name="salvar em Excel").first.click()

            filename = self.ofx_dir + "/" + self.create_filename("_fev.xlsx")
            self.save_file_from_page(download_info, filename)

    def exit(self, page):
        page.get_by_role("button", name=" sair").click()

    # @param page: Playwright page object
    # @param data: Dictionary with bank parameters
    def run(self, page, data):
        agencia = data.get("agencia")
        conta   = data.get("conta")
        senha   = data.get("senha")

        self.log("Starting login")
        self.__login(page, agencia, conta, senha)

        self.log("Starting extrato")
        self.__extrato(page)

        self.log("Getting OFX")
        ofx = self.__get_ofx(page)
        if not ofx:
            raise Exception("Failed to get OFX")

        self.log("Getting Credit Card")
        self.__get_credit_card(page)

        self.log("Exiting")
        self.exit(page)

        return self.json_return(Status.OK, "Task Completed", ofx)

@click.command()
@click.option('-h', '--headless', default=False, is_flag=True, help='Run in headless mode')
def command(headless):
    with open('config.json', 'r') as f:
        config = json.load(f)

    bot = Itau(headless = headless)

    ret = bot.start(config.get("itau"))
    print(ret)

if __name__ == "__main__":
    command()
