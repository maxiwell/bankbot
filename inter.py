import requests
import time
import random
import re
import sys
from datetime import datetime, timedelta
import json
import click

from bankbot import *

class Inter(BankBot):

    def __init__(self, headless, token, debug):
        super().__init__(headless, debug)
        self.token = token
        self.auth_file = ".auth"
        self.auth_token = ""

    def init(self):
        self.base_url  = 'https://contadigital.inter.co/home'
        self.bank_name = 'Inter'

    def __token(self, page):

        def intercept_request(request):
            headers = request.headers
            if "authorization" in headers:
                token = headers["authorization"]
                if token is not None:
                    with open(self.auth_file, "w") as f:
                        f.write(token)

        # Adiciona o listener para capturar requisições
        page.on("request", intercept_request)

        self.log("Abrindo a tela para validar QR Code")
        page.goto(self.base_url)

        page.locator("//span[contains(text(), 'Conta digital PF')]").click()
        page.locator("//button[contains(text(), 'Estou ciente')]").click()

        page.get_by_test_id("itemInício").wait_for(timeout = 60000)

    def __extrato(self, page, conta):
        headers = {
                'sec-ch-ua-platform': '"Windows"',
                'referer': '',
                'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'sec-ch-ua': '"Not(A:Brand";v="99", "Chromium";v="133")',
                'x-inter-organization': 'IBPF',
                'sec-ch-ua-mobile': '?0',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'accept': 'application/json, text/plain, */*',
                'x-inter-conta-corrente': f'{conta}',
                'authorization': f'{self.auth_token}'
        }

        today = datetime.today().strftime("%d-%m-%Y")
        last_30_days = (datetime.today() - timedelta(days=30)).strftime("%d-%m-%Y")

        response = requests.get(f"https://cd.web.bancointer.com.br/ib-pfj/cc/extrato/exportar/v2?formato=OFX&data-inicio={last_30_days}&data-fim={today}", headers = headers)

        if response.status_code != 200:
            return self.json_return(Status.ERROR, "Erro ao consultar o extrato, tente renovar o token")

        del headers['authorization']

        file = response.json().get('fileUrl')
        response = requests.get(file, stream = True, headers = headers)

        self.save_file_from_request(response, 'arquivo_baixado.ofx')

        """ Deprecated version: clicking in the 'Exportar' element'
        page.get_by_test_id("itemConta Digital").hover()
        page.get_by_test_id("containerSubMenuSaldo e Extrato").get_by_role("button", name="Extrato").click()
        page.get_by_role("button", name="Exportar").click()
        """

        return self.json_return(Status.OK, "OFX baixado com sucesso")


    # @param page: Playwright page object
    # @param data: Dictionary with bank parameters
    def run(self, page, data):
        conta = data.get("conta")

        if self.token:
            try:
                self.log("Get token")
                self.__token(page)
            except Exception as e:
                print(str(e))
                return self.json_return(Status.ERROR, "Problema ao renovar o token")

            return self.json_return(Status.OK, "Token salvo")
        else:
            with open(self.auth_file, "r") as f:
                self.auth_token = f.read()


        self.log("Starting extrato")
        ret = self.__extrato(page, conta)

        return ret


@click.command()
@click.option('-h', '--headless', default=False, is_flag=True, help='Run in headless mode')
@click.option('-t', '--token', default=False, is_flag=True, help='Renew the auth token')
@click.option('-d', '--debug', default=False, is_flag=True, help='Print all request data')
def command(headless, token, debug):
    with open('config.json', 'r') as f:
        config = json.load(f)

    bot = Inter(headless, token, debug)

    ret = bot.start(config.get("inter"))
    print(ret)

if __name__ == "__main__":
    command()
