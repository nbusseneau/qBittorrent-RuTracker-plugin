import configparser
from .rtapi import Connection, Sort, OrderBy


class rutracker:
    def __init__(self, config_file: str):
        config = configparser.ConfigParser()
        config.read(config_file)
        self.config = config["rutracker"]
        self.conn = self.connect()

    def connect(self):
        conn = Connection(
            self.config["username"],
            self.config["password"]
        )
        order_by = self.config.get("order_by")
        if order_by:
            conn.order_by = getattr(OrderBy, order_by)
        sort = self.config.get("sort")
        if sort:
            conn.sort = getattr(Sort, sort)
        return conn