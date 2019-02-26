import logging
import voluptuous as vol
import asyncio
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_ICON, CONF_NAME, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_TOGGLE, STATE_ON, STATE_OFF)
import vlc

REQUIREMENTS = ['python-vlc']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'doorbell'
CONF_MEDIA = 'media'
CONF_VOLUME = 'volume'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: cv.schema_with_slug_keys(
        vol.Any({
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_MEDIA): cv.string,
            vol.Optional(CONF_VOLUME, default=100): vol.All(vol.Coerce(int), vol.Range(min=0,max=100)),
            vol.Optional(CONF_ICON): cv.icon,
        }, None)
    )
}, extra=vol.ALLOW_EXTRA)

vlc_instance = vlc.Instance()

@bind_hass
def is_on(hass, entity_id):
    return hass.states.is_state(entity_id, STATE_ON)

async def async_setup(hass, config):
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        media = cfg.get(CONF_MEDIA)
        volume = cfg.get(CONF_VOLUME)
        icon = cfg.get(CONF_ICON)
        _LOGGER.info('adding %s with volume %s' % (media, volume))
        entities.append(DoorBell(object_id, name, media, volume, icon))

    if not entities:
        return False

    component.async_register_entity_service(
        SERVICE_TURN_ON, SERVICE_SCHEMA,
        'async_turn_on'
    )

    component.async_register_entity_service(
        SERVICE_TURN_OFF, SERVICE_SCHEMA,
        'async_turn_off'
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE, SERVICE_SCHEMA,
        'async_toggle'
    )

    await component.async_add_entities(entities)
    return True

class DoorBell(ToggleEntity):

    def __init__(self, object_id, name, filepath, volume,  icon):
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._filepath = filepath
        self._state = STATE_OFF
        self._volume = volume
        self._icon = icon
        self._length = None

        # if _should_stop == True, stop playing
        self._should_stop = False
        media = vlc_instance.media_new_path(self._filepath)
        self._player = vlc_instance.media_player_new()
        self._player.set_media(media) 
        _LOGGER.info('Setting volume to %s for %s' % (self._volume, self._filepath)) 
        v = self._player.audio_set_volume(self._volume)
        if v == -1:
            _LOGGER.error('could not set volume %s' % self._volume)
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._sound_finished)
        events.event_attach(vlc.EventType.MediaPlayerPlaying, self._sound_playing)


    # called by vlc when it has reached the end of a media play
    def _sound_finished(self, data):
        # this is called in a separated thread (not managed by us)
        _LOGGER.debug('reached end of play, stopping')
        self._should_stop = True

    # vlc starts playing, get_length() is not available before this
    def _sound_playing(self, data):
        # this is called in a separated thread (not managed by us)
        if self._length == None:
            self._length = self._player.get_length()
        _LOGGER.debug('start playing %s, length=%s' % (self._filepath, self._length))

    # check for finished plays and stop
    async def _background_check(self):
        while True:
            await asyncio.sleep(.5)
            if self._should_stop:
                self._should_stop = False
                await self.async_turn_off()

    # bugged, using this will cause hass to hang
    # def _schedule_stop(self, length):
    #    return run_coroutine_threadsafe(
    #            self._async_schedule_stop(length), self.hass.loop).result()

    #async def _async_schedule_stop(self, seconds):
    #    await asyncio.sleep(seconds)
    #    await self.async_turn_off()
    #    _LOGGER.debug('stopped playing %s' % self._filepath)

    async def async_added_to_hass(self):
        # If not None, we got an initial value.
        await super().async_added_to_hass()
        self._state = STATE_OFF
        asyncio.ensure_future(self._background_check(), loop=self.hass.loop)
        #self.hass.async_create_task(self._background_check())

    async def async_turn_on(self, **kwargs):
        if self._state == STATE_ON:
            return
        self._state = STATE_ON
        await self.async_update_ha_state()
        self._player.play()

    async def async_turn_off(self, **kwargs):
        if self._state == STATE_OFF:
            return
        self._state = STATE_OFF
        self._player.stop()
        await self.async_update_ha_state()

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def is_on(self):
        return self._state == STATE_ON

    @property
    def length(self):
        return self._length

