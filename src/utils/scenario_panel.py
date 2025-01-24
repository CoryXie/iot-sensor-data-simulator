from nicegui import ui
from typing import Dict, List, Callable
from datetime import datetime, time
from src.constants.device_templates import SCENARIO_TEMPLATES
from loguru import logger

class ScenarioPanel:
    """Class to handle scenario management and scheduling"""
    
    def __init__(self, on_scenario_change: Callable[[str], None]):
        self.current_scenario = None
        self.on_scenario_change = on_scenario_change
        self.scheduled_scenarios = []
        self.details_container = None
        logger.debug("Initialized ScenarioPanel utility component")
        
    def create_panel(self):
        """Create the scenario panel"""
        logger.info("Creating scenario panel")
        with ui.column().classes('w-full gap-4'):
            # Scenario selection
            with ui.row().classes('w-full items-center gap-2'):
                scenario_select = ui.select(
                    options=list(SCENARIO_TEMPLATES.keys()),
                    label='Select Scenario',
                    on_change=lambda e: self._update_scenario(e.value)
                ).classes('w-full')
                
                # Time selection
                time_input = ui.input('Time (HH:MM)', value='12:00').classes('w-32')
                
                # Schedule button
                ui.button('Schedule', on_click=lambda: self._schedule_scenario(
                    scenario_select.value, time_input.value)).classes('bg-blue-500 text-white')
            
            # Scenario details
            with ui.card().classes('w-full'):
                ui.label('Scenario Details').classes('text-subtitle1')
                self.details_container = ui.column().classes('w-full')
                self._update_scenario_details()
            
            # Scheduled scenarios list
            with ui.card().classes('w-full'):
                ui.label('Scheduled Changes').classes('text-subtitle1')
                self.schedule_container = ui.column().classes('w-full')
                self._update_scheduled_list()
        logger.debug("Scenario panel created successfully")
    
    def _validate_time(self, value: str) -> bool:
        """Validate time input format"""
        logger.debug(f"Validating time input: {value}")
        if not value:
            logger.warning("Empty time value provided")
            return False
        try:
            hour, minute = map(int, value.split(':'))
            valid = 0 <= hour < 24 and 0 <= minute < 60
            logger.debug(f"Time validation result: {valid}")
            return valid
        except:
            logger.warning(f"Invalid time format: {value}")
            return False
    
    def _handle_add_schedule(self):
        """Handle adding a new schedule"""
        logger.debug("Handling add schedule request")
        if not self.schedule_scenario.value:
            logger.warning("No scenario selected for scheduling")
            ui.notify('Please select a scenario', type='warning')
            return
            
        if not self.schedule_time.value:
            logger.warning("No time provided for scheduling")
            ui.notify('Please enter a time', type='warning')
            return
            
        try:
            hour, minute = map(int, self.schedule_time.value.split(':'))
            time_obj = time(hour=hour, minute=minute)
            
            self.scheduled_scenarios.append({
                'scenario': self.schedule_scenario.value,
                'time': time_obj
            })
            
            self._update_scheduled_list()
            logger.info(f"Successfully scheduled {self.schedule_scenario.value} for {time_obj.strftime('%H:%M')}")
            ui.notify('Schedule added successfully', type='positive')
            
            # Clear inputs
            self.schedule_time.value = ''
            self.schedule_scenario.value = None
            
        except Exception as e:
            error_msg = f'Error adding schedule: {str(e)}'
            logger.error(error_msg)
            ui.notify(error_msg, type='negative')
    
    def _update_scenario_details(self):
        """Update the scenario details display"""
        try:
            logger.debug("Updating scenario details")
            if not self.details_container or not self.details_container.client:
                logger.warning("Details container not available")
                return
                
            self.details_container.clear()
            if not self.current_scenario:
                logger.debug("No current scenario selected")
                with self.details_container:
                    ui.label('No scenario selected')
                return
                
            scenario = SCENARIO_TEMPLATES.get(self.current_scenario)
            if not scenario:
                logger.warning(f"Scenario template not found for {self.current_scenario}")
                return
                
            with self.details_container:
                ui.label(scenario.get('description', '')).classes('text-sm')
                if 'devices' in scenario:
                    with ui.expansion('Devices').classes('w-full'):
                        for device in scenario['devices']:
                            ui.label(f"• {device}").classes('text-sm')
            logger.debug(f"Updated details for scenario: {self.current_scenario}")
        except Exception as e:
            logger.exception(f"Error updating scenario details: {str(e)}")
    
    async def _update_scenario(self, scenario_name: str):
        """Update the scenario display"""
        try:
            if self.scenario_name_label and self.scenario_name_label.client:
                with self.scenario_name_label:
                    self.scenario_name_label.clear()
                    self.scenario_name_label.text = scenario_name or 'No active scenario'
            
            if self.on_scenario_change:
                await self.on_scenario_change(scenario_name)
            
        except Exception as e:
            logger.exception(f"Error updating scenario: {str(e)}")
    
    def _update_scheduled_list(self):
        """Update the list of scheduled scenarios"""
        try:
            logger.debug("Updating scheduled scenarios list")
            if not self.schedule_container or not self.schedule_container.client:
                logger.warning("Schedule container not available")
                return
                
            self.schedule_container.clear()
            with self.schedule_container:
                ui.label('Scheduled Changes').classes('text-h6 mt-4')
                if not self.scheduled_scenarios:
                    logger.debug("No scheduled scenarios to display")
                    ui.label('No scheduled changes').classes('text-sm')
                    return
                    
                for schedule in sorted(self.scheduled_scenarios, key=lambda x: x['time']):
                    with ui.card().classes('w-full p-2 mb-2'):
                        with ui.row().classes('w-full items-center justify-between'):
                            ui.label(f"{schedule['scenario']} at {schedule['time'].strftime('%H:%M')}")
                            ui.button(icon='delete', on_click=lambda s=schedule: self._remove_schedule(s))
            logger.debug(f"Updated list with {len(self.scheduled_scenarios)} scheduled scenarios")
        except Exception as e:
            logger.exception(f"Error updating scheduled list: {str(e)}")
    
    def _remove_schedule(self, schedule: Dict):
        """Remove a scheduled scenario change"""
        logger.info(f"Removing scheduled scenario: {schedule['scenario']} at {schedule['time'].strftime('%H:%M')}")
        if schedule in self.scheduled_scenarios:
            self.scheduled_scenarios.remove(schedule)
            self._update_scheduled_list()
            ui.notify('Schedule removed', type='info')
            logger.debug("Schedule removed successfully")
    
    def process_scheduled_scenarios(self):
        """Process scheduled scenarios and trigger changes"""
        try:
            current_time = datetime.now().time()
            logger.debug(f"Processing scheduled scenarios at {current_time.strftime('%H:%M')}")
            
            # Check each scheduled scenario
            for schedule in self.scheduled_scenarios[:]:  # Create a copy to avoid modification during iteration
                schedule_time = schedule['time']
                
                # If it's time to change the scenario
                if (current_time.hour == schedule_time.hour and 
                    current_time.minute == schedule_time.minute):
                    logger.info(f"Triggering scheduled scenario change to {schedule['scenario']}")
                    self._update_scenario(schedule['scenario'])
                    self.scheduled_scenarios.remove(schedule)
                    self._update_scheduled_list()
                    ui.notify(f"Scheduled scenario change to {schedule['scenario']}", type='info')
            return True  # Keep the timer running
        except Exception as e:
            logger.exception(f"Error processing scheduled scenarios: {str(e)}")
            return True  # Keep the timer running 