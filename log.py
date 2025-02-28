from datetime import datetime

class Log:

    def __init__(self, tag, log_file):
        self.tag = tag
        self.log_file = log_file

    def __log(self, message):
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        string = f"[{ts}] {self.tag}: {message}"

        print(string)

        if self.log_file is not None:
            with open(self.log_file, "a") as a:
                a.write(string + "\n")

    def info(self, message):
        self.__log(message)
