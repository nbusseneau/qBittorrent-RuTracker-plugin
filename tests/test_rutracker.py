from pathlib import Path

from pytest import mark, fail
from qbit_rutracker.rtapi import Connection, ResultsPage


samples_dir = Path(__file__).parent.joinpath("samples")


def test_connection(pytestconfig):
    login = pytestconfig.getoption("--username")
    password = pytestconfig.getoption("--password")
    if not login or not password:
        raise ValueError("Provide credentials via --username and --password.")
    conn = Connection(login=login, password=password)


@mark.unit
def test_sample_page():
    html = samples_dir.joinpath("sample.html").read_text()
    page = ResultsPage(html)
    table = page.soup.find("table", **{"class": "forumline"})
    assert table
    assert page.has_topics()
    assert page.current_user() == "username"
    assert page.has_next()
    elem = next(iter(page))
    assert elem["name"] == (
        "[Фильмы 1991-2000] Форрест Гамп / Forrest Gump (Роберт Земекис / Robert Zemeckis)"
        " [1994, США, Драма, мелодрама, BDRip-AVC] MVO (Позитив) + Original (Eng) + Sub (Rus, Eng)"
    )
    assert elem["desc_link"] == "/forum/viewtopic.php?t=4948966"
    assert elem["size"] == 1557370878 #1556925644
    assert elem["link"] == "/forum/dl.php?t=4948966"
    assert elem["seeds"] == 259
    assert elem["leech"] == 9

@mark.unit
def test_empty_page():
    html = samples_dir.joinpath("empty.html").read_text()
    page = ResultsPage(html)
    assert not page.has_topics()
    assert list(page) == []
