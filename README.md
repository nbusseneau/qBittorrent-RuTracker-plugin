qBittorent rutracker.org plugin
===============================

qBittorrent search engine plugin for rutracker.org.

Nothing fancy, it follows the [writing plugin guide recommandations](https://github.com/qbittorrent/qBittorrent/wiki/How-to-write-a-search-plugin).

Installation
------------
First, [download `rutracker.py`](https://raw.github.com/Skymirrh/qBittorent-rutracker-plugin/master/rutracker.py) and edit lines 26 and 27 by replacing `your_username` and `your_password` with your rutracker.org username and password.

Then just use qBittorrent interface to add the modified `rutracker.py` to your search engines.

If you wish to have an icon displayed next to it in the engines list, [download `rutracker.ico`](https://github.com/Skymirrh/qBittorent-rutracker-plugin/raw/master/rutracker.ico) and move it  to `AppData\Local\qBittorrent\nova\engines` or the Unix equivalent (I guess it would be something like `~/.local/share/data/qBittorrent/nova/engines`).
