# ha-doorbell
A doorbell component for Home Assistant

### Installation
Copy `doorbell.py` to `CONFIG/custom_components` folder

### Use
add to configuration.yaml:

```yaml
doorbell:
  bell1:
    media: /media/bell1.mp3
    
 bell2:
    media: /media/bell2.mp3
```

Calling `doorbell.turn_on` with `entity_id = bell1` will ring `bell1`.
