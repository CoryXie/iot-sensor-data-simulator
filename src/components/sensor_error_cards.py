from nicegui import ui
from src.constants.sensor_errors import *
import json


class AnomalyCard:
    '''Anomaly card component for displaying input fields for anomaly generation'''

    def __init__(self):
        '''Initializes the anomaly card and sets up the UI elements'''
        with ui.row().classes('mt-4 p-4 gap-0 w-full bg-gray-100 rounded-md'):
            with ui.column().classes('gap-1'):
                ui.label('Wahrscheinlichkeiten').classes('mt-2 font-bold')
                ui.label('Definiere mit welcher Wahrscheinlichkeit Anomalien auftreten sollen.').classes(
                    'text-[13px] opacity-80')
            with ui.grid().classes('mt-3 mb-4 w-full sm:grid-cols-3'):
                self.probability_pos_anomaly_input = ui.number(
                    label='Wkt. für pos. Anomalien', value=5, min=0, max=100, suffix='%')
                self.probability_neg_anomaly_input = ui.number(
                    label='Wkt. für neg. Anomalien', value=2, min=0, max=100, suffix='%')

            with ui.column().classes('gap-1'):
                ui.label('Abweichungsbereiche').classes('mt-4 font-bold')
                ui.label('Definiere den Wertebereich, in dem Anomalien entstehen können.').classes(
                    'text-[13px] opacity-80')
            with ui.grid().classes('mt-3 pb-4 w-full sm:grid-cols-3'):
                with ui.column().classes('gap-0'):
                    ui.label('Positiv').classes('font-medium opacity-70')
                    self.pos_anomaly_upper_range_input = ui.number(
                        label='Maximal', value=20, min=0, max=100).classes('w-full')
                    self.pos_anomaly_lower_range_input = ui.number(
                        label='Minimal', value=20, min=0, max=100).classes('w-full')

                with ui.column().classes('gap-0'):
                    ui.label('Negativ').classes('font-medium opacity-70')
                    self.neg_anomaly_upper_range_input = ui.number(
                        label='Maximal', value=15, min=0, max=100).classes('w-full')
                    self.neg_anomaly_lower_range_input = ui.number(
                        label='Minimal', value=5, min=0, max=100).classes('w-full')

    def get_values(self, json_dump=False):
        '''Returns the values of the input fields as a dictionary'''
        values = {
            "type": ANOMALY,
            PROBABILITY_POS_ANOMALY: self.probability_pos_anomaly_input.value / 100,
            PROBABILITY_NEG_ANOMALY: self.probability_neg_anomaly_input.value / 100,
            POS_ANOMALY_UPPER_RANGE: self.pos_anomaly_upper_range_input.value,
            POS_ANOMALY_LOWER_RANGE: self.pos_anomaly_lower_range_input.value,
            NEG_ANOMALY_UPPER_RANGE: self.neg_anomaly_upper_range_input.value,
            NEG_ANOMALY_LOWER_RANGE: self.neg_anomaly_lower_range_input.value
        }

        # Return values as JSON string if json_dump is True
        if json_dump:
            return json.dumps(values)

        return values


class MCARCard:
    '''MCAR card component for displaying input fields for MCAR generation'''

    def __init__(self):
        '''Initializes the MCAR card and sets up the UI elements'''
        with ui.row().classes('mt-4 p-4 gap-0 w-full bg-gray-100 rounded-md'):
            with ui.column().classes('gap-1'):
                ui.label('Wahrscheinlichkeit').classes('mt-2 font-bold')
                ui.label('Definiere mit welcher Wahrscheinlichkeit Werte komplett zufällig fehlen sollen.').classes(
                    'text-[13px] opacity-80')
            with ui.grid(columns=3).classes('mt-3 mb-4 w-full'):
                self.probability_input = ui.number(
                    label='Wahrscheinlichkeit', value=5, min=0, max=100, suffix='%')

    def get_values(self, json_dump=False):
        '''Returns the values of the input fields as a dictionary'''
        values = {
            "type": MCAR,
            PROBABILITY: self.probability_input.value / 100
        }

        # Return values as JSON string if json_dump is True
        if json_dump:
            return json.dumps(values)

        return values
    
class DuplicateDataCard:
    '''Duplicate data card component for displaying input fields for duplicate data generation'''

    def __init__(self):
        '''Initializes the duplicate data card and sets up the UI elements'''
        with ui.row().classes('mt-4 p-4 gap-0 w-full bg-gray-100 rounded-md'):
            with ui.column().classes('gap-1'):
                ui.label('Wahrscheinlichkeit').classes('mt-2 font-bold')
                ui.label('Definiere mit welcher Wahrscheinlichkeit doppelte Daten generiert werden sollen.').classes(
                    'text-[13px] opacity-80')
            with ui.grid(columns=3).classes('mt-3 mb-4 w-full'):
                self.probability_input = ui.number(
                    label='Wahrscheinlichkeit', value=5, min=0, max=100, suffix='%')

    def get_values(self, json_dump=False):
        '''Returns the values of the input fields as a dictionary'''
        values = {
            "type": DUPLICATE_DATA,
            PROBABILITY: self.probability_input.value / 100
        }

        # Return values as JSON string if json_dump is True
        if json_dump:
            return json.dumps(values)

        return values
    
class DriftCard:
    '''Drift card component for displaying input fields for drift generation'''

    def __init__(self):
        '''Initializes the drift card and sets up the UI elements'''
        with ui.row().classes('mt-4 p-4 gap-0 w-full bg-gray-100 rounded-md'):
            with ui.column().classes('gap-1'):
                ui.label('Wahrscheinlichkeit').classes('mt-2 font-bold')
                ui.label('Definiere nach wie vielen Iterationen n ein linearer Drift eintreten soll und gib die Driftgrößen an.').classes(
                    'text-[13px] opacity-80')
            with ui.grid().classes('mt-3 mb-4 w-full sm:grid-cols-3'):
                self.after_n_iterations_input = ui.number(label='Ab n Iterationen', value=5, min=0, max=100)
                self.average_drift_rate_input = ui.number(label='Driftrate', value=1, min=0, max=10)
                self.variation_range_input = ui.number(label='Variationsbereich', value=0.1, min=0, format='%.2f')
                
    def get_values(self, json_dump=False):
        '''Returns the values of the input fields as a dictionary'''
        values = {
            "type": DRIFT,
            AFTER_N_ITERATIONS: int(self.after_n_iterations_input.value),
            AVERAGE_DRIFT_RATE: self.average_drift_rate_input.value,
            VARIATION_RANGE: self.variation_range_input.value
        }

        # Return values as JSON string if json_dump is True
        if json_dump:
            return json.dumps(values)

        return values
