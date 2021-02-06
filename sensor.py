"""Support for monitoring the qBittorrent API."""
import logging

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    DATA_RATE_KILOBYTES_PER_SECOND,
    STATE_IDLE,
    PERCENTAGE,
    TIME_MINUTES,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_CURRENT_STATUS = "current_status"
SENSOR_TYPE_DOWNLOAD_SPEED = "download_speed"
SENSOR_TYPE_UPLOAD_SPEED = "upload_speed"
SENSOR_TYPE_TOTAL_NUMBER = "number_total"
SENSOR_TYPE_HIGHEST_ETA = "highest_eta"
SENSOR_TYPE_DOWNLOAD_NUMBER = "number_downloading"
SENSOR_TYPE_SEED_NUMBER = "number_seeding"
SENSOR_TYPE_PAUSED_NUMBER = "number_paused"
SENSOR_TYPE_DOWNLOAD_PERCENT = "download_percent"


DEFAULT_NAME = "qBittorrent"

SENSOR_TYPES = {
    SENSOR_TYPE_CURRENT_STATUS: ["Status", None],
    SENSOR_TYPE_DOWNLOAD_SPEED: ["Down Speed", DATA_RATE_KILOBYTES_PER_SECOND],
    SENSOR_TYPE_UPLOAD_SPEED: ["Up Speed", DATA_RATE_KILOBYTES_PER_SECOND],
    SENSOR_TYPE_TOTAL_NUMBER: ["Total Torrents", None],
    SENSOR_TYPE_HIGHEST_ETA: ["Highest ETA", TIME_MINUTES],
    SENSOR_TYPE_DOWNLOAD_NUMBER: ["Torrents Downloading", None],
    SENSOR_TYPE_SEED_NUMBER: ["Torrents Seeding", None],
    SENSOR_TYPE_PAUSED_NUMBER: ["Torrents Paused", None],
    SENSOR_TYPE_DOWNLOAD_PERCENT: ["Download Percentage", PERCENTAGE],


}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the qBittorrent sensors."""

    try:
        client = Client(config[CONF_URL])
        client.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    except LoginRequired:
        _LOGGER.error("Invalid authentication")
        return
    except RequestException as err:
        _LOGGER.error("Connection failed")
        raise PlatformNotReady from err

    name = config.get(CONF_NAME)

    dev = []
    for sensor_type in SENSOR_TYPES:
        sensor = QBittorrentSensor(sensor_type, client, name, LoginRequired)
        dev.append(sensor)

    add_entities(dev, True)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentSensor(Entity):
    """Representation of an qBittorrent sensor."""

    def __init__(self, sensor_type, qbittorrent_client, client_name, exception):
        """Initialize the qBittorrent sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.client = qbittorrent_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._available = False
        self._exception = exception

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return true if device is available."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from qBittorrent and updates the state."""
        try:
            data = self.client.sync_main_data()
            torrents = data["torrents"]
            self._available = True
        except RequestException:
            _LOGGER.error("Connection lost")
            self._available = False
            return
        except self._exception:
            _LOGGER.error("Invalid authentication")
            return

        if data is None:
            return

        download = data["server_state"]["dl_info_speed"]
        upload = data["server_state"]["up_info_speed"]

        if self.type == SENSOR_TYPE_CURRENT_STATUS:
            if upload > 0 and download > 0:
                self._state = "up_down"
            elif upload > 0 and download == 0:
                self._state = "seeding"
            elif upload == 0 and download > 0:
                self._state = "downloading"
            else:
                self._state = STATE_IDLE
        elif self.type == SENSOR_TYPE_TOTAL_NUMBER:
            self._state = len(data["torrents"])
        elif self.type == SENSOR_TYPE_DOWNLOAD_NUMBER:
            downloading = [n for n in torrents if torrents[n]["state"] == "downloading" or torrents[n]["state"] == "forceDL"]
            self._state = len(downloading)
        elif self.type == SENSOR_TYPE_SEED_NUMBER:
            seeding = [n for n in torrents if torrents[n]["state"] == "stalledUP" or torrents[n]["state"] == "forcedUP" or torrents[n]["state"] == "queuedUP"]
            self._state = len(seeding)
        elif self.type == SENSOR_TYPE_DOWNLOAD_PERCENT:
            total = 0
            downloaded = 0
            percentage = 0
            for n in torrents:
                if torrents[n]["state"] == "downloading" or torrents[n]["state"] == "forcedDL" or torrents[n]["state"] == "pausedDL":
                    total = total + torrents[n]["size"]
                    downloaded = downloaded + torrents[n]["downloaded"]
            if total != 0: percentage = round(downloaded / total * 100, 2)
            self._state = percentage
        elif self.type == SENSOR_TYPE_PAUSED_NUMBER:
            paused = [n for n in torrents if torrents[n]["state"] == "pausedDL"]
            self._state = len(paused)
        elif self.type == SENSOR_TYPE_HIGHEST_ETA:
            torrents = data["torrents"]
            highest_eta = 0
            for torrent in torrents:
                if (torrents[torrent]["eta"] > highest_eta):
                    highest_eta = round(torrents[torrent]["eta"] / 60 , 2)
            self._state = highest_eta
        elif self.type == SENSOR_TYPE_DOWNLOAD_SPEED:
            self._state = format_speed(download)
        elif self.type == SENSOR_TYPE_UPLOAD_SPEED:
            self._state = format_speed(upload)
