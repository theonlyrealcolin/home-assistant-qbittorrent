# home-assistant-qbittorrent
### Enhanced qBittorrent integration for Home Assistant
#### Place inside your custom integrations folder and it will replace the default qBittorent integration.


## Adds the following sensors
* Total Torrents
* Number Downloading Torrents
* Number Seeding Torrents
* Number Paused Torrents
* Highest Torrent ETA (in minutes)
* Percentage of All Downloading and Paused Torrents Finished (Total Downloaded Size / Total Size)

#### Example config entry
```yaml
sensor:
  - platform: qbittorrent
    url: "http://<hostname>:<port>"
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
