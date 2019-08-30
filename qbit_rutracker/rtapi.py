from enum import Enum
import logging
import re
import typing as ty
import time

import humanfriendly
import requests
from bs4 import BeautifulSoup, element

log = logging.getLogger(__name__)


class Sort(Enum):
    Ascending = 1
    Descending = 2


class OrderBy(Enum):
    Registered = 1
    TopicName = 2
    Downloads = 4
    Size = 7
    Seeds = 10
    Leeches = 11


def dict_encode(mapping: dict, encoding="cp1251"):
    """Encode dict values to encoding."""
    for key, value in mapping.items():
        if not isinstance(value, str):
            raise NotImplementedError(f"{value} types is not supported")
        mapping[key] = value.encode(encoding)
    return mapping


class Connection(requests.Session):
    """ Connection to the RuTracker. """

    user_agent = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/76.0.3809.110 Safari/537.36 Vivaldi/2.7.1628.30"
    )
    hosts = ["rutracker.org", "rutracker.net", "rutracker.nl", "rutracker.cr"]

    def __init__(self, login, password, mask_useragent=False):
        super().__init__()
        self.host = self._find_host()
        self.mask_useragent = mask_useragent
        self.username = login
        self.login(login=login, password=password)

        self.order_by = OrderBy.Seeds
        self.sort = Sort.Descending

    def _find_host(self) -> str:
        for host in self.hosts:
            host = "https://" + host
            try:
                self.get(host)
                log.debug("Connected to host %s.", host)
                return host
            except requests.RequestException:
                log.info("Failed to connect to %s", host)
        raise requests.ConnectionError("Failed to connect to any of the mirrors.")

    def sendreq(
        self, method: str, url: str, params=None, data=None
    ) -> requests.Response:
        """ Sends new HTTP request to the current RuTracker endpoint. """
        return self.request(
            method=method,
            url=self.host + url,
            params=params,
            data=data,
            headers={"User-Agent": self.user_agent} if self.mask_useragent else None,
            allow_redirects=False,
        )

    def login(self, login: str, password: str):
        """ Performs authorization and saves cookies. """
        credentials = dict(login_username=login, login_password=password, login="Вход")
        dict_encode(credentials)
        response = self.sendreq("post", "/forum/login.php", data=credentials)
        if response.status_code != 302:
            log.debug("Response body: \n%s", response.text)
            raise RuntimeError(
                "Authorization response code" f"{response.status_code} - maybe captcha?"
            )

    def dump_cookies(self) -> ty.List[ty.Tuple[str, str]]:
        return self.cookies.items()

    def load_cookies(self, raw_items: ty.List[ty.Tuple[str, str]]):
        for name, value in raw_items:
            self.cookies.set(name, value)

    def search_request(
        self, text: str, start=0, order_by: OrderBy = None, sort: Sort = None
    ) -> str:
        order_by = order_by or self.order_by
        sort = sort or self.sort
        params = {"nm": text, "start": start}
        data = dict(f=[-1], o=order_by.value, s=sort.value, nm=text.encode("cp1251"))
        response = self.sendreq("post", "/forum/tracker.php", params=params, data=data)
        if not response.ok:
            log.debug("Response body: \n%s", response.text)
            raise ValueError(f"Search response code {response.status_code}")
        return response.text

    def search(
        self, text: str, start=0, order_by: OrderBy = None, sort: Sort = None
    ) -> ty.Iterable[dict]:
        response_text = self.search_request(text=text, start=start, order_by=order_by, sort=sort)
        page = ResultsPage(response_text, host=self.host)
        user = page.current_user()
        if user != self.username:
            log.warning("Current user is %s - what?", user)
        if not page.has_topics():
            return
        while 1:
            yield from page
            if not page.has_next():
                break
            start += len(page)
            # just to not load rutracker too much
            time.sleep(0.4)
            response_text = self.search_request(
                text=text, start=start, order_by=order_by, sort=sort
            )
            page = ResultsPage(response_text)


class ResultsPage:
    """ Wrapper around BeautifulSoup with """

    def __init__(self, markup, host=""):
        self.soup = BeautifulSoup(markup=markup, features="html.parser")
        self.table = self.get_table()
        self.host = host

    def current_user(self) -> str:
        return self.soup.find("a", id="logged-in-username").string

    def get_table(self) -> element.Tag:
        """ Returns table with the topic rows """
        return self.soup.find("table", **{"class": "forumline"})

    def has_topics(self) -> bool:
        elem = self.table.find("td", string=re.compile("Не найдено"))
        return not bool(elem)

    def has_next(self) -> ty.Optional[bool]:
        info = self.soup.find("div", **{"class": "bottom_info"})
        if not info:
            return
        current, total = (
            info.find("div", **{"class": "nav"})
            .find("p", style="float: left")
            .find_all("b")
        )
        return int(current.string) < int(total.string)

    def __iter__(self):
        if not self.has_topics():
            return
        for row in self.table.find("tbody").find_all("tr"):
            elem = {
                k: None
                for k in ("cat", "name", "link", "size", "seeds", "leech", "desc_link")
            }
            title = row.find("div", **{"class": "t-title"}).a
            category = row.find("div", **{"class": "f-name"}).a.string
            elem["name"] = f"[{category}] " + title.text
            elem["desc_link"] = self.host + "/forum/" + title.get("href")
            size_col = row.find("td", **{"class": "tor-size"})
            elem["size"] = humanfriendly.parse_size(size_col.get("data-ts_text"), binary=True)
            # size column also contains download link
            elem["link"] = self.host + "/forum/" + size_col.a.get("href")
            seeds = row.find("b", {"class": "seedmed"})
            elem["seeds"] = int(seeds.string) if seeds is not None else 0
            elem["leech"] = int(row.find("td", {"class": "leechmed"}).string)
            yield elem

    def __len__(self):
        if not self.has_topics():
            return 0
        return sum(1 for _ in self.table.find("tbody").find_all("tr"))
