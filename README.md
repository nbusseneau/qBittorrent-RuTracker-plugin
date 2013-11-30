qBittorent rutracker.org plugin
===============================

qBittorrent search engine plugin for rutracker.org.

Nothing fancy, it follows the [writing plugin guide recommandations](https://github.com/qbittorrent/qBittorrent/wiki/How-to-write-a-search-plugin).

Installation
------------
First, edit lines 26 and 27 of `rutracker.py` and input your rutracker.org username and password.
Then just use qBittorrent interface to add `rutracker.py` to your search engines.
If you wish to have an icon displayed next to it in the engines list, move `rutracker.ico`  to `AppData\Local\qBittorrent\nova\engines` or the Unix equivalent (I guess it would be something like `~/.local/share/data/qBittorrent/nova/engines`).
