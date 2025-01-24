from nicegui import ui

class LogsDialog():
    '''This class represents the logs dialog. It is used to display the logs of an active container.'''

    def __init__(self, parent, show=False):
        '''Initializes the logs dialog'''
        self.parent = parent
        self.dialog = None
        self.log = None
        self.setup(show)

    def setup(self, show):
        '''Sets up the UI elements of the dialog'''
        with self.parent:
            with ui.dialog(value=show) as dialog, ui.card().classes('w-full'):
                self.dialog = dialog
                ui.label(
                    f'Logs').classes('text-lg font-semibold')
                self.log = ui.log().classes('w-full h-48')
                ui.button('Schließen', on_click=dialog.close).props(
                    'flat').classes('self-end')
                
    def show(self):
        '''Shows the dialog'''
        self.dialog.open()
    