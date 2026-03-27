# Campus Management Configuration Sub-App

This module handles the governance limits for the campus management module. 
It uses the central `Configuration` model from the `configuration` app with a dedicated `sub_app` namespace (`campus_management`).

## How to used in Campus Management Service:

```python
from configuration.campus_management.config_service import CampusManagementConfiguration

def your_creation_method():
    # 1. Check building limit
    current_count = Building.objects.count()
    limit = CampusManagementConfiguration.get_building_limit()
    
    if current_count >= limit:
        raise ValidationError(f"Building creation limit of {limit} reached.")

    # 2. Check floor limit
    floor_limit = CampusManagementConfiguration.get_floor_limit_per_building()
    # ... logic here

    # 3. Check venues per floor limit
    venue_limit = CampusManagementConfiguration.get_venues_per_floor_limit()
    # ... logic here
```

## Available Configuration Keys (Sub-App: `campus_management`):
| Key | Default Value | Description |
| :--- | :--- | :--- |
| `building_creation_limit` | 100 | Max number of buildings allowed. |
| `venues_per_floor_limit` | 20 | Max number of venues (rooms) per floor. |
| `floor_limit_per_building` | 50 | Max number of floors per building. |

## How to Set New Limits:
You can set these limits via Django admin (search for `Configuration` with `sub_app='campus_management'`) or programmatically:

```python
CampusManagementConfiguration.set_setting("building_creation_limit", 200, "Increase building limit for CampusExpansion")
```
