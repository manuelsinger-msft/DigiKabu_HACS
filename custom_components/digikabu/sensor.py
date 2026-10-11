"""Uninterpreted student API responses with successful retrieval timestamps."""

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import JSONValue
from .const import BASE_URL, DOMAIN
from .coordinator import DigiKabuConfigEntry, DigiKabuCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DigiKabuConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a stable sensor per documented read endpoint."""
    async_add_entities(
        DigiKabuSensor(entry, coordinator)
        for coordinator in entry.runtime_data.coordinators.values()
    )


class DigiKabuSensor(CoordinatorEntity[DigiKabuCoordinator], SensorEntity):
    """The timestamp indicates retrieval, not an invented API event date."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, entry: DigiKabuConfigEntry, coordinator: DigiKabuCoordinator
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{coordinator.endpoint}"
        self._attr_translation_key = coordinator.endpoint
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="DigiKabu",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=BASE_URL,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the last successful retrieval time."""
        return self.coordinator.data.fetched_at if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict[str, JSONValue]:
        """Keep the original JSON structure rather than guessing field names."""
        if self.coordinator.data is None:
            return {}
        return {"response": self.coordinator.data.response}
