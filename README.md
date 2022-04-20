# qBittorrent RuTracker plugin

qBittorrent search engine plugin for RuTracker.
The plugin conforms to [qBittorrent's search plugin API/specifications](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin).

In case [rutracker.org](https://rutracker.org) is DNS blocked, the plugin will try to reach [official RuTracker mirrors](http://rutracker.wiki/%D0%A7%D1%82%D0%BE_%D0%B4%D0%B5%D0%BB%D0%B0%D1%82%D1%8C,_%D0%B5%D1%81%D0%BB%D0%B8_%D0%B2%D0%B0%D0%BC_%D0%B7%D0%B0%D0%B1%D0%BB%D0%BE%D0%BA%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD_%D0%B4%D0%BE%D1%81%D1%82%D1%83%D0%BF_%D0%BD%D0%B0_rutracker.org#.D0.97.D0.B5.D1.80.D0.BA.D0.B0.D0.BB.D0.B0_rutracker.org) instead.
You may also configure your own mirrors.

## Installation

- [Download the latest release.](https://github.com/nbusseneau/qBittorrent-RuTracker-plugin/releases/latest)
- Open `rutracker.py` with a text editor, and replace `YOUR_USERNAME_HERE` and `YOUR_PASSWORD_HERE` with your RuTracker username and password.
- Move `rutracker.py` and `rutracker.png` to qBittorrent search engines directory:
  - Windows: `%localappdata%\qBittorrent\nova3\engines\`
  - Linux: `~/.local/share/qBittorrent/nova3/engines/`
  - OS X: `~/Library/Application Support/qBittorrent/nova3/engines/`
- RuTracker search engine should now be available in qBittorrent.

## Magnet links support (for web GUI)

The default version of the plugin downloads torrents via torrent files, which is not supported by the web GUI for now.
An alternative version of the plugin is provided and able to download via magnet links instead.
If you want to use it, uncomment `download_type` in the `Config` section.

Do note that using magnet links is currently NOT recommended for most use cases.

## Troubleshooting

If you get no results from RuTracker when you search something, please:

- Check that at least one mirror from the list of [official RuTracker mirrors](http://rutracker.wiki/%D0%A7%D1%82%D0%BE_%D0%B4%D0%B5%D0%BB%D0%B0%D1%82%D1%8C,_%D0%B5%D1%81%D0%BB%D0%B8_%D0%B2%D0%B0%D0%BC_%D0%B7%D0%B0%D0%B1%D0%BB%D0%BE%D0%BA%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD_%D0%B4%D0%BE%D1%81%D1%82%D1%83%D0%BF_%D0%BD%D0%B0_rutracker.org#.D0.97.D0.B5.D1.80.D0.BA.D0.B0.D0.BB.D0.B0_rutracker.org) is working.
- Check that you are not captcha-blocked (try to manually connect to the website: after logging in once, the captcha will disappear and the script will work).
- Check that the script credentials are correct (try to manually connect to the website by copy/pasting username and password from `rutracker.py`).
- If it still does not work, [please file a bug report](https://github.com/nbusseneau/qBittorrent-RuTracker-plugin/issues/new/choose).
