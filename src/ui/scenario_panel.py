from nicegui import ui
from typing import Dict, Callable
from constants.device_templates import SCENARIO_TEMPLATES
from datetime import datetime, time
from loguru import logger

class ScenarioPanel:
    """Scenario control panel component"""
    def __init__(self, on_scenario_change: Callable = None):
        self.current_scenario = "Home"
        self.on_scenario_change = on_scenario_change
        self.scheduled_scenarios = []
        logger.debug("Initialized ScenarioPanel UI component")

    def create_panel(self):
        """Create the scenario control panel"""
        logger.info("Creating scenario control panel")
        with ui.card().classes('w-full'):
            ui.label('Smart Home Control Panel').classes('text-h6')
            
            # Current scenario selection
            with ui.row().classes('w-full items-center'):
                ui.label('Current Scenario:')
                scenario_select = ui.select(
                    options=list(SCENARIO_TEMPLATES.keys()),
                    value=self.current_scenario
                ).classes('w-48')
                
                def handle_scenario_change(e):
                    logger.info(f"Changing scenario to: {e.value}")
                    self.current_scenario = e.value
                    if self.on_scenario_change:
                        self.on_scenario_change(e.value)
                
                scenario_select.on('change', handle_scenario_change)

            # Scenario details
            with ui.card().classes('w-full q-mt-md'):
                ui.label('Scenario Details').classes('text-subtitle1')
                with ui.row().classes('w-full'):
                    self.details_container = ui.column().classes('w-full')
                self._update_scenario_details()

            # Schedule scenario
            with ui.card().classes('w-full q-mt-md'):
                ui.label('Schedule Scenario').classes('text-subtitle1')
                with ui.row().classes('w-full items-center gap-4'):
                    scenario = ui.select(
                        options=list(SCENARIO_TEMPLATES.keys()),
                        value=self.current_scenario
                    ).classes('w-48')
                    
                    time_input = ui.time().classes('w-32')
                    
                    def handle_schedule():
                        if scenario.value and time_input.value:
                            logger.info(f"Scheduling scenario {scenario.value} for {time_input.value}")
                            self._add_scheduled_scenario(scenario.value, time_input.value)
                    
                    ui.button('Schedule', on_click=handle_schedule)

            # Scheduled scenarios list
            with ui.card().classes('w-full q-mt-md'):
                ui.label('Scheduled Changes').classes('text-subtitle1')
                self.schedule_container = ui.column().classes('w-full')
                self._update_scheduled_list()
        logger.debug("Scenario control panel created successfully")

    def _update_scenario_details(self):
        """Update the scenario details display"""
        logger.debug(f"Updating scenario details for {self.current_scenario}")
        self.details_container.clear()
        
        scenario = SCENARIO_TEMPLATES[self.current_scenario]
        with self.details_container:
            ui.label(f"Description: {scenario['description']}")
            
            with ui.row().classes('w-full'):
                with ui.column().classes('w-1/3'):
                    ui.label('Temperature:')
                    temp_adj = scenario['sensor_adjustments']['temperature']
                    ui.label(f"Offset: {temp_adj['offset']}°C")
                    ui.label(f"Variation: ±{temp_adj['variation']}°C")
                
                with ui.column().classes('w-1/3'):
                    ui.label('Motion:')
                    motion_prob = scenario['sensor_adjustments']['motion']['probability']
                    ui.label(f"Activity: {motion_prob * 100}%")
                
                with ui.column().classes('w-1/3'):
                    ui.label('Energy:')
                    energy_factor = scenario['sensor_adjustments']['energy']['factor']
                    ui.label(f"Usage: {energy_factor * 100}%")
        logger.debug("Scenario details updated successfully")

    def _add_scheduled_scenario(self, scenario_name: str, schedule_time: str):
        """Add a scheduled scenario change"""
        logger.info(f"Adding scheduled scenario: {scenario_name} at {schedule_time}")
        try:
            # Parse the time string
            hour, minute = map(int, schedule_time.split(':'))
            schedule_time = time(hour, minute)
            
            # Add to scheduled scenarios
            self.scheduled_scenarios.append({
                'scenario': scenario_name,
                'time': schedule_time,
                'added': datetime.now()
            })
            
            # Sort by time
            self.scheduled_scenarios.sort(key=lambda x: x['time'])
            
            # Update the display
            self._update_scheduled_list()
            
            ui.notify(f'Scheduled {scenario_name} for {schedule_time.strftime("%H:%M")}')
            logger.info(f"Successfully scheduled {scenario_name} for {schedule_time.strftime('%H:%M')}")
        except Exception as e:
            error_msg = f'Error scheduling scenario: {str(e)}'
            logger.error(error_msg)
            ui.notify(error_msg, type='negative')

    def _update_scheduled_list(self):
        """Update the list of scheduled scenarios"""
        logger.debug("Updating scheduled scenarios list")
        self.schedule_container.clear()
        
        with self.schedule_container:
            if not self.scheduled_scenarios:
                ui.label('No scheduled changes')
                logger.debug("No scheduled scenarios to display")
                return
            
            for schedule in self.scheduled_scenarios:
                with ui.card().classes('w-full q-pa-sm q-mb-sm'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label(f"{schedule['scenario']} at {schedule['time'].strftime('%H:%M')}")
                        
                        def create_delete_handler(schedule_time):
                            def handle_delete():
                                logger.info(f"Deleting scheduled scenario at {schedule_time.strftime('%H:%M')}")
                                self.scheduled_scenarios = [
                                    s for s in self.scheduled_scenarios 
                                    if s['time'] != schedule_time
                                ]
                                self._update_scheduled_list()
                            return handle_delete
                        
                        ui.button(icon='delete', on_click=create_delete_handler(schedule['time']))
            logger.debug(f"Updated list with {len(self.scheduled_scenarios)} scheduled scenarios")

    def process_scheduled_scenarios(self, current_time: time = None):
        """Process scheduled scenarios and trigger changes"""
        if current_time is None:
            current_time = datetime.now().time()
        
        logger.debug(f"Processing scheduled scenarios at {current_time.strftime('%H:%M')}")
        triggered = []
        for schedule in self.scheduled_scenarios:
            if schedule['time'] <= current_time:
                logger.info(f"Triggering scheduled scenario: {schedule['scenario']}")
                if self.on_scenario_change:
                    self.on_scenario_change(schedule['scenario'])
                triggered.append(schedule)
        
        # Remove triggered scenarios
        if triggered:
            logger.info(f"Removing {len(triggered)} triggered scenarios")
            self.scheduled_scenarios = [
                s for s in self.scheduled_scenarios 
                if s not in triggered
            ]
            self._update_scheduled_list()
            
        return triggered 