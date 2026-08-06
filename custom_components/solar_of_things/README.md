# Solar of Things custom integration

## Notes for Home Assistant UI polish

This integration now exposes device-level status and energy sensors based on the newest Solar of Things API payloads:

- current generation power
- online/offline status
- device state
- today/month/year/total generation totals

It also exposes inverter writeable controls where the API supports them, including:

- operating mode (output source priority)
- charger source priority
- grid charging / feed-in switches
- backup mode
- battery charge and discharge limits
- grid charge limit

These entities are created as native Home Assistant number/select/switch entities so they behave like standard controls in the dashboard and entity list.
