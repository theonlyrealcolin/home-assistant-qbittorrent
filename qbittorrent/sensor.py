"""Support for monitoring the qBittorrent API."""
from __future__ import annotations

import logging

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    STATE_IDLE,
    PERCENTAGE,
    TIME_MINUTES,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN

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

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TYPE_CURRENT_STATUS,
        name="Status",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED,
        name="Down Speed",
        icon="mdi:cloud-download",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED,
        name="Up Speed",
        icon="mdi:cloud-upload",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
        SensorEntityDescription(
        key=SENSOR_TYPE_TOTAL_NUMBER,
        name="Total Torrents",
        icon="mdi:cloud-upload"
    ),
        SensorEntityDescription(
        key=SENSOR_TYPE_HIGHEST_ETA,
        name="Highest ETA",
        icon="mdi:cloud-upload",

        native_unit_of_measurement=TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
        SensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_NUMBER,
        name="Torrents Downloading",
        icon="mdi:cloud-upload",

    ),
       SensorEntityDescription(
        key=SENSOR_TYPE_SEED_NUMBER,
        name="Torrents Seeding",
        icon="mdi:cloud-upload",

    ),
       SensorEntityDescription(
        key=SENSOR_TYPE_PAUSED_NUMBER,
        name="Torrents Paused",
        icon="mdi:cloud-upload",

    ),
       SensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_PERCENT,
        name="Download Percentage",
        icon="mdi:cloud-upload",
        native_unit_of_measurement=PERCENTAGE

    ),

)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the qBittorrent platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.6.0",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entites: AddEntitiesCallback,
) -> None:
    """Set up qBittorrent sensor entries."""
    client: Client = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        QBittorrentSensor(description, client, config_entry)
        for description in SENSOR_TYPES
    ]
    async_add_entites(entities, True)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentSensor(SensorEntity):
    """Representation of an qBittorrent sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        qbittorrent_client: Client,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the qBittorrent sensor."""
        self.entity_description = description
        self.client = qbittorrent_client

        self._attr_unique_id = f"{config_entry.entry_id}-{description.key}"
        self._attr_name = f"{config_entry.title} {description.name}"
        self._attr_available = False

    def update(self) -> None:
        """Get the latest data from qBittorrent and updates the state."""
        try:
            data = self.client.sync_main_data()
            torrents = data["torrents"]
            self._attr_available = True
        except RequestException:
            _LOGGER.error("Connection lost")
            self._attr_available = False
            return
        except LoginRequired:
            _LOGGER.error("Invalid authentication")
            return

        if data is None:
            return

        download = data["server_state"]["dl_info_speed"]
        upload = data["server_state"]["up_info_speed"]

        sensor_type = self.entity_description.key
        if sensor_type == SENSOR_TYPE_CURRENT_STATUS:
            if upload > 0 and download > 0:
                self._attr_native_value = "up_down"
            elif upload > 0 and download == 0:
                self._attr_native_value = "seeding"
            elif upload == 0 and download > 0:
                self._attr_native_value = "downloading"
            else:
                self._attr_native_value = STATE_IDLE
        elif sensor_type == SENSOR_TYPE_TOTAL_NUMBER:
            self._attr_native_value = len(data["torrents"])
        elif sensor_type == SENSOR_TYPE_DOWNLOAD_NUMBER:
            downloading = [n for n in torrents if torrents[n]["state"] == "downloading" or torrents[n]["state"] == "forceDL"]
            self._attr_native_value = len(downloading)
        elif sensor_type == SENSOR_TYPE_SEED_NUMBER:
            seeding = [n for n in torrents if torrents[n]["state"] == "stalledUP" or torrents[n]["state"] == "forcedUP" or torrents[n]["state"] == "queuedUP"]
            self._attr_native_value = len(seeding)
        elif sensor_type == SENSOR_TYPE_DOWNLOAD_PERCENT:
            total = 0
            downloaded = 0
            percentage = 0
            for n in torrents:
                if torrents[n]["state"] == "downloading" or torrents[n]["state"] == "forcedDL" or torrents[n]["state"] == "pausedDL":
                    total = total + torrents[n]["size"]
                    downloaded = downloaded + torrents[n]["downloaded"]
            if total != 0: percentage = round(downloaded / total * 100, 2)
            self._attr_native_value = percentage
        elif sensor_type == SENSOR_TYPE_PAUSED_NUMBER:
            paused = [n for n in torrents if torrents[n]["state"] == "pausedDL"]
            self._attr_native_value = len(paused)
        elif sensor_type == SENSOR_TYPE_HIGHEST_ETA:
            torrents = data["torrents"]
            highest_eta = 0
            for torrent in torrents:
                if (torrents[torrent]["eta"] > highest_eta):
                    highest_eta = round(torrents[torrent]["eta"] / 60 , 2)
            self._attr_native_value = highest_eta
        elif sensor_type == SENSOR_TYPE_DOWNLOAD_SPEED:
            self._attr_native_value = format_speed(download)
        elif sensor_type == SENSOR_TYPE_UPLOAD_SPEED:
            self._attr_native_value = format_speed(upload)
