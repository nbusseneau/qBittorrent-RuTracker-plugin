import configparser
import logging

import humanize
from novaprinter import prettyPrinter

from . import rtapi
from .rtapi import Connection, Sort, OrderBy


class rutracker:
    """ qbittorrent search API interface implementation. """
    name = "RuTracker"
    # We MUST produce an URL attribute at instantiation time, otherwise qBittorrent
    # will fail to register the engine, see #15
    url = "https://rutracker.org"

    def __init__(self, config_file: str):
        config = configparser.ConfigParser()
        config.read(config_file)
        self.config = config["rutracker"]
        self.conn = self.connect()
        self.log = self.get_logger()
        self.log.info("Rutracker plugin loaded.")

    def get_logger(self):
        log = logging.getLogger(__name__)
        log.setLevel(logging.INFO)
        rtapi.log.setLevel(logging.INFO)
        filename = self.config.get("error_log")
        if filename:
            logging.basicConfig(filename=filename, level=logging.WARNING)
        return log

    def connect(self) -> Connection:
        conn = Connection(self.config["username"], self.config["password"])
        order_by = self.config.get("order_by")
        if order_by:
            conn.order_by = getattr(OrderBy, order_by)
        sort = self.config.get("sort")
        if sort:
            conn.sort = getattr(Sort, sort)
        return conn

    def search(self, what, cat="all"):
        try:
            for torrent in self.conn.search(what):
                self.log.debug("Processing torrent %s", torrent["name"])
                # According to documentation,
                # "size => A string corresponding to the torrent size
                # (i.e: "6 MB" or "200 KB" or "1.2 GB"...)"
                # so we have to humanize size
                torrent["size"] = humanize.naturalsize(torrent["size"])
                torrent["engine_url"] = "https://rutracker.org"  # Kludge, see #15
                prettyPrinter(torrent)
        except:
            self.log.exception("Got error on search")


    def download_torrent(self, url):
        return self.conn.download_torrent(url=url)