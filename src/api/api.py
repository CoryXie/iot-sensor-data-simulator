"""REST API for controlling Smart Home devices"""

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Path
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
import logging

from src.database import get_db as get_db_session
from src.models.device import Device
from src.models.sensor import Sensor
from src.models.room import Room
from src.utils.smart_home_simulator import SmartHomeSimulator
from src.utils.event_system import EventSystem

# Configure logger
logger = logging.getLogger(__name__)

# Create API router
api_router = APIRouter(prefix="/api", tags=["smart-home"])

# -------------------------------
# Pydantic models for API
# -------------------------------

class ACMode(int, Enum):
    AUTO = 0
    COOL = 1 
    HEAT = 2
    FAN = 3
    DRY = 4

class ThermostatMode(int, Enum):
    AUTO = 0
    COOL = 1
    HEAT = 2
    FAN = 3

class BlindsMode(int, Enum):
    MANUAL = 0
    AUTO_LIGHT = 1
    SCHEDULED = 2

class ACSettings(BaseModel):
    power: bool = Field(..., description="True to turn on, False to turn off")
    temperature: float = Field(..., ge=16, le=30, description="Target temperature in Celsius (16-30)")
    mode: ACMode = Field(..., description="Operation mode (0: Auto, 1: Cool, 2: Heat, 3: Fan, 4: Dry)")
    fan_speed: int = Field(..., ge=1, le=5, description="Fan speed (1-5)")

class ThermostatSettings(BaseModel):
    power: bool = Field(..., description="True to turn on, False to turn off")
    temperature: float = Field(..., ge=16, le=30, description="Target temperature in Celsius (16-30)")
    mode: ThermostatMode = Field(..., description="Operation mode (0: Auto, 1: Cool, 2: Heat, 3: Fan)")

class BlindsSettings(BaseModel):
    position: int = Field(..., ge=0, le=100, description="Blinds position in percentage (0-100)")
    mode: BlindsMode = Field(..., description="Operation mode (0: Manual, 1: Auto Light-based, 2: Scheduled)")

class IrrigationSettings(BaseModel):
    schedule_enabled: bool = Field(..., description="True to enable automatic watering schedule")
    
class IrrigationAction(BaseModel):
    action: str = Field(..., description="Action to perform (water_now)")
    duration: Optional[int] = Field(5, ge=1, le=30, description="Duration in minutes (1-30)")

class DeviceInfo(BaseModel):
    id: int
    name: str
    type: str
    room_id: Optional[int] = None
    room_name: Optional[str] = None
    is_active: bool
    sensors: List[Dict[str, Any]]

# -------------------------------
# API Endpoints
# -------------------------------

@api_router.get("/devices", response_model=List[DeviceInfo])
def get_devices(
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    room_id: Optional[int] = Query(None, description="Filter by room ID"),
    db: Session = Depends(get_db_session)
):
    """
    Get all devices or filter by type or room
    """
    try:
        query = db.query(Device)
        
        if device_type:
            query = query.filter(Device.type == device_type)
        
        if room_id:
            query = query.filter(Device.room_id == room_id)
            
        devices = query.all()
        
        result = []
        for device in devices:
            # Get room name if available
            room_name = None
            if device.room_id:
                room = db.query(Room).filter(Room.id == device.room_id).first()
                room_name = room.name if room else None
            
            # Get sensor data
            sensors_data = []
            for sensor in device.sensors:
                sensors_data.append({
                    "id": sensor.id,
                    "name": sensor.name,
                    "type": sensor.type,
                    "value": sensor.current_value,
                    "unit": sensor.unit
                })
                
            # Create device info
            device_info = {
                "id": device.id,
                "name": device.name,
                "type": device.type,
                "room_id": device.room_id,
                "room_name": room_name,
                "is_active": device.is_active,
                "sensors": sensors_data
            }
            
            result.append(device_info)
            
        return result
        
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving devices: {str(e)}")


@api_router.get("/devices/{device_id}", response_model=DeviceInfo)
def get_device(
    device_id: int = Path(..., description="The ID of the device to retrieve"),
    db: Session = Depends(get_db_session)
):
    """
    Get detailed information about a specific device
    """
    try:
        device = db.query(Device).filter(Device.id == device_id).first()
        
        if not device:
            raise HTTPException(status_code=404, detail=f"Device with ID {device_id} not found")
        
        # Get room name if available
        room_name = None
        if device.room_id:
            room = db.query(Room).filter(Room.id == device.room_id).first()
            room_name = room.name if room else None
        
        # Get sensor data
        sensors_data = []
        for sensor in device.sensors:
            sensors_data.append({
                "id": sensor.id,
                "name": sensor.name,
                "type": sensor.type,
                "value": sensor.current_value,
                "unit": sensor.unit
            })
            
        # Create device info
        device_info = {
            "id": device.id,
            "name": device.name,
            "type": device.type,
            "room_id": device.room_id,
            "room_name": room_name,
            "is_active": device.is_active,
            "sensors": sensors_data
        }
        
        return device_info
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving device: {str(e)}")


@api_router.post("/ac/{device_id}/control")
def control_ac(
    device_id: int = Path(..., description="The ID of the AC device to control"),
    settings: ACSettings = Body(..., description="AC settings to apply"),
    db: Session = Depends(get_db_session)
):
    """
    Control a whole home AC system
    """
    try:
        # Verify device exists and is an AC
        device = db.query(Device).filter(Device.id == device_id, Device.type == "hvac_system").first()
        
        if not device:
            raise HTTPException(status_code=404, detail=f"AC device with ID {device_id} not found")
        
        # Get simulator instance
        simulator = SmartHomeSimulator.get_instance()
        
        # Apply settings
        success = simulator.set_ac_parameters(
            power=settings.power,
            temperature=settings.temperature,
            mode=settings.mode,
            fan_speed=settings.fan_speed
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to apply AC settings")
            
        return {"success": True, "message": "AC settings applied successfully"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error controlling AC {device_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error controlling AC: {str(e)}")


@api_router.post("/thermostat/{device_id}/control")
def control_thermostat(
    device_id: int = Path(..., description="The ID of the thermostat to control"),
    settings: ThermostatSettings = Body(..., description="Thermostat settings to apply"),
    db: Session = Depends(get_db_session)
):
    """
    Control a room thermostat
    """
    try:
        # Verify device exists and is a thermostat
        device = db.query(Device).filter(Device.id == device_id, Device.type == "thermostat").first()
        
        if not device:
            raise HTTPException(status_code=404, detail=f"Thermostat with ID {device_id} not found")
        
        # Get room ID
        room_id = device.room_id
        if not room_id:
            raise HTTPException(status_code=400, detail="Thermostat is not associated with a room")
        
        # Get simulator instance
        simulator = SmartHomeSimulator.get_instance()
        
        # Apply settings
        success = simulator.set_thermostat(
            room_id=room_id,
            power=settings.power,
            temperature=settings.temperature,
            mode=settings.mode
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to apply thermostat settings")
            
        return {"success": True, "message": "Thermostat settings applied successfully"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error controlling thermostat {device_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error controlling thermostat: {str(e)}")


@api_router.post("/blinds/{device_id}/control")
def control_blinds(
    device_id: int = Path(..., description="The ID of the blinds to control"),
    settings: BlindsSettings = Body(..., description="Blinds settings to apply"),
    db: Session = Depends(get_db_session)
):
    """
    Control smart blinds
    """
    try:
        # Verify device exists and is blinds
        device = db.query(Device).filter(Device.id == device_id, Device.type == "blinds").first()
        
        if not device:
            raise HTTPException(status_code=404, detail=f"Blinds with ID {device_id} not found")
        
        # Get room ID
        room_id = device.room_id
        if not room_id:
            raise HTTPException(status_code=400, detail="Blinds are not associated with a room")
        
        # Get simulator instance
        simulator = SmartHomeSimulator.get_instance()
        
        # Apply settings
        success = simulator.set_blinds(
            room_id=room_id,
            position=settings.position,
            mode=settings.mode
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to apply blinds settings")
            
        return {"success": True, "message": "Blinds settings applied successfully"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error controlling blinds {device_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error controlling blinds: {str(e)}")


@api_router.post("/irrigation/{device_id}/schedule")
def set_irrigation_schedule(
    device_id: int = Path(..., description="The ID of the irrigation system to control"),
    settings: IrrigationSettings = Body(..., description="Irrigation schedule settings"),
    db: Session = Depends(get_db_session)
):
    """
    Set irrigation schedule
    """
    try:
        # Verify device exists and is an irrigation system
        device = db.query(Device).filter(Device.id == device_id, Device.type == "irrigation").first()
        
        if not device:
            raise HTTPException(status_code=404, detail=f"Irrigation system with ID {device_id} not found")
        
        # Find schedule sensor
        schedule_sensor = db.query(Sensor).filter(
            Sensor.device_id == device_id,
            Sensor.type == "schedule"
        ).first()
        
        if not schedule_sensor:
            raise HTTPException(status_code=404, detail="Schedule sensor not found")
            
        # Update schedule value
        schedule_sensor.current_value = 1 if settings.schedule_enabled else 0
        db.commit()
        
        # Get event system to emit update
        event_system = EventSystem()
        event_system.trigger('sensor_update', {
            'id': schedule_sensor.id,
            'device_id': device_id,
            'name': schedule_sensor.name,
            'value': schedule_sensor.current_value,
            'unit': schedule_sensor.unit
        })
            
        return {
            "success": True, 
            "message": f"Irrigation schedule {'enabled' if settings.schedule_enabled else 'disabled'}"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error setting irrigation schedule {device_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting irrigation schedule: {str(e)}")


@api_router.post("/irrigation/{device_id}/action")
def irrigation_action(
    device_id: int = Path(..., description="The ID of the irrigation system to control"),
    action_data: IrrigationAction = Body(..., description="Irrigation action to perform"),
    db: Session = Depends(get_db_session)
):
    """
    Perform irrigation actions (water now)
    """
    try:
        # Verify device exists and is an irrigation system
        device = db.query(Device).filter(Device.id == device_id, Device.type == "irrigation").first()
        
        if not device:
            raise HTTPException(status_code=404, detail=f"Irrigation system with ID {device_id} not found")
        
        # Validate action
        if action_data.action.lower() != "water_now":
            raise HTTPException(status_code=400, detail=f"Invalid action: {action_data.action}")
        
        # Find flow sensor
        flow_sensor = db.query(Sensor).filter(
            Sensor.device_id == device_id,
            Sensor.type == "flow"
        ).first()
        
        if not flow_sensor:
            raise HTTPException(status_code=404, detail="Flow sensor not found")
            
        # Update flow value to simulate watering
        flow_sensor.current_value = 5.0  # 5 L/min flow rate
        db.commit()
        
        # Get event system to emit update
        event_system = EventSystem()
        event_system.trigger('sensor_update', {
            'id': flow_sensor.id,
            'device_id': device_id,
            'name': flow_sensor.name,
            'value': flow_sensor.current_value,
            'unit': flow_sensor.unit
        })
        
        # Schedule reset after duration (would need a task queue in production)
        # For now, just acknowledge
            
        return {
            "success": True, 
            "message": f"Irrigation started for {action_data.duration} minutes"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error executing irrigation action {device_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing irrigation action: {str(e)}")


@api_router.get("/rooms")
def get_rooms(db: Session = Depends(get_db_session)):
    """
    Get all rooms with their devices
    """
    try:
        rooms = db.query(Room).all()
        
        result = []
        for room in rooms:
            devices = []
            for device in room.devices:
                devices.append({
                    "id": device.id,
                    "name": device.name,
                    "type": device.type
                })
                
            result.append({
                "id": room.id,
                "name": room.name,
                "room_type": room.room_type,
                "devices": devices
            })
            
        return result
        
    except Exception as e:
        logger.error(f"Error getting rooms: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving rooms: {str(e)}") 