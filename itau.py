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

        # 'networkidle' nunca dispara de forma confiável no Itau (a pagina
        # mantem polling/analytics); espera direto pelo teclado de senha
        page.wait_for_selector('.teclas.clearfix a', timeout=60000)

        print("typing password")
        self.__enter_password(page, senha)


    def __extrato(self, page):
        show_button = '#saldo-extrato-card-accordion'
        ver_extrato = 'button[aria-label="ver extrato"]'

        # espera o dashboard renderizar o botao ou o accordion, o que vier primeiro
        page.wait_for_selector(f'{ver_extrato}, {show_button}', timeout=60000)
        time.sleep(random.randint(2,4))

        if not page.is_visible(ver_extrato):
            page.click(show_button)

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

        #page.wait_for_load_state('networkidle')


    def __get_ofx(self, page):
        page.get_by_role("button", name="salvar como").wait_for()
        page.get_by_role("button", name="salvar como").click()

        # Start waiting for the download
        with page.expect_download() as download_info:

            # Perform the action that initiates download
            page.get_by_role("button", name="salvar em OFX").click()

            filename = self.ofx_dir + "/" + self.create_filename(".ofx")
            return self.save_file_from_page(download_info, filename)


    def __open_cards_page(self, page):
        page.get_by_role("link", name=" menu").hover()
        page.get_by_role("link", name="cartões").click()

        # espera a lista de cartoes renderizar ('attached', pois o container
        # pode estar recolhido/invisivel)
        page.locator("#conteudo0").wait_for(state='attached', timeout=60000)
        time.sleep(random.randint(2,4))

    def __download_fatura(self, page, card_idx):
        opcoes = page.locator("#botao-opcoes-lancamentos")
        opcoes.wait_for(timeout=60000)
        time.sleep(random.randint(2,4))

        # Mes Atual
        opcoes.click()
        with page.expect_download() as download_info:

            page.get_by_role("button", name="salvar em Excel").first.click()
            #page.get_by_role("button", name="salvar planilha").click()

            filename = self.ofx_dir + "/" + self.create_filename(f"_card{card_idx}.xlsx")
            self.save_file_from_page(download_info, filename)

        ## Mes Anterior
        #page.get_by_role("tab", name="fevereiro: Fatura fechada R$").click()
        #page.locator("#botao-opcoes-lancamentos").click()

        #with page.expect_download() as download_info:
        #    page.get_by_role("button", name="salvar em Excel").first.click()

        #    filename = self.ofx_dir + "/" + self.create_filename("_fev.xlsx")
        #    self.save_file_from_page(download_info, filename)

    def __get_credit_card(self, page):
        self.__open_cards_page(page)

        num_cards = 0
        while page.locator(f"#conteudo{num_cards}").count() > 0:
            num_cards += 1

        self.log(f"Found {num_cards} credit card(s)")

        for i in range(num_cards):
            if i > 0:
                # a pagina de fatura substitui a lista de cartoes; volta pelo menu
                self.__open_cards_page(page)

            card = page.locator(f"#conteudo{i}")
            if card.count() == 0:
                break

            ver_fatura = card.get_by_role("link", name="ver fatura")

            # cartoes recolhidos precisam ser expandidos antes
            if not ver_fatura.is_visible():
                expand = page.locator(f"#detalharCartao{i}")
                if expand.count() > 0:
                    expand.scroll_into_view_if_needed()
                    expand.click()
                    time.sleep(random.randint(1,2))

            if not ver_fatura.is_visible():
                self.log(f"Card {i}: 'ver fatura' not available, skipping")
                continue

            self.log(f"Card {i}: downloading fatura")
            ver_fatura.scroll_into_view_if_needed()
            ver_fatura.click()

            self.__download_fatura(page, i)

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

        return self.json_return(Status.OK, "Task Completed")

@click.command()
@click.option('-h', '--headless', default=False, is_flag=True, help='Run in headless mode')
@click.option('-d', '--debug', default=False, is_flag=True, help='Run in debug mode')
def command(headless, debug):
    with open('config.json', 'r') as f:
        config = json.load(f)

    bot = Itau(headless = headless, debug = debug)

    ret = bot.start(config.get("itau"))

if __name__ == "__main__":
    command()
