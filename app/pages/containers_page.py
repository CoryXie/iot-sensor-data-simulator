from nicegui import ui
from components.navigation import Navigation
from components.container_card import ContainerCard
from components.live_view_dialog import LiveViewDialog
from model.container import Container
from model.device import Device


class ContainersPage:

    def __init__(self, iot_hub_helper):
        self.iot_hub_helper = iot_hub_helper
        self.containers = Container.get_all()
        self.cards_grid = None
        self.cards = []
        self.update_stats()
        self.setup_layout()
        self.setup_menu_bar()
        self.setup_cards_grid()
        self.setup_live_view_dialog()

    def setup_layout(self):
        Navigation()
        ui.query('main').classes('h-px')
        ui.query('.nicegui-content').classes('p-8')
        ui.label("Container").classes('text-2xl font-bold')

    def setup_menu_bar(self):
        with ui.row().classes('px-4 w-full flex items-center justify-between h-20 bg-gray-200 rounded-lg shadow-md'):
            ui.button('Neuen Container erstellen',
                      on_click=lambda: self.open_create_container_dialog()).classes('')

            with ui.row():
                with ui.row().classes('ml-4 gap-1'):
                    ui.label('Gesamt:').classes('text-sm font-medium')
                    ui.label().classes('text-sm').bind_text(self, 'containers_count')
                with ui.row().classes('ml-4 gap-1'):
                    ui.label('Aktiv:').classes('text-sm font-medium')
                    ui.label().classes('text-sm').bind_text(self, 'active_containers_count')
                with ui.row().classes('ml-4 gap-1'):
                    ui.label('Inaktiv:').classes('text-sm font-medium')
                    ui.label().classes('text-sm').bind_text(self, 'inactive_containers_count')

            with ui.row():
                self.filter_input = ui.input(
                    placeholder='Filter', on_change=self.filter_handler).classes('w-44')
                ui.select({1: "Alle", 2: "Aktiv", 3: "Inaktiv"},
                          value=1).classes('w-24')

    def setup_cards_grid(self):
        self.cards_grid = ui.grid().classes(
            'relative mt-6 w-full grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4')
        self.setup_note_label()

        if len(self.containers) == 0:
            self.show_note("Keine Container vorhanden")
        else:
            with self.cards_grid:
                for container in self.containers:
                    new_container_card = ContainerCard(wrapper=self.cards_grid, container=container, start_callback=self.start_container,
                                                        stop_callback=self.stop_container, delete_callback=self.delete_container, live_view_callback=self.show_live_view_dialog)
                    self.cards.append(new_container_card)

    def setup_note_label(self):
        with self.cards_grid:
            self.note_label = ui.label().classes('absolute left-1/2 top-48 self-center -translate-x-1/2')
            self.note_label.set_visibility(False)

    def setup_live_view_dialog(self):
        self.live_view_dialog = LiveViewDialog(self.cards_grid)

        for container in self.containers:
            container.live_view_dialog = self.live_view_dialog

    def update_stats(self):
        self.containers_count = len(self.containers)
        self.active_containers_count = len(
            list(filter(lambda c: c.is_active, self.containers)))
        self.inactive_containers_count = self.containers_count - self.active_containers_count

    def filter_handler(self):
        search_text = self.filter_input.value
        results = list(filter(lambda c: search_text.lower()
                       in c.container.name.lower(), self.cards))

        for card in self.cards:
            card.visible = card in results

        if len(results) == 0:
            self.show_note("Kein Treffer")
        else:
            self.hide_note()

    def show_note(self, message):
        self.cards_grid.classes('justify-center')
        self.note_label.text = message
        self.note_label.set_visibility(True)

    def hide_note(self):
        self.cards_grid.classes('justify-start')
        self.note_label.set_visibility(False)

    def open_create_container_dialog(self):
        with ui.dialog(value=True) as dialog, ui.card().classes('w-full min-h-[500px]'):
            with ui.stepper().props('vertical').classes('w-full h-full') as stepper:
                with ui.step('Allgemein'):
                    with ui.column():
                        name_input = ui.input('Name*')
                        description_input = ui.input(
                            'Beschreibung (max. 255 Zeichen)').classes('w-full')
                        location_input = ui.input('Standort').classes('w-full')
                    with ui.stepper_navigation():
                        ui.button('Abbrechen', on_click=lambda: dialog.close()).props(
                            'flat')
                        ui.button('Weiter', on_click=lambda: self.check_container_name_input(
                            stepper, name_input))
                with ui.step('Geräte'):
                    devices = Device.get_all_unassigned()

                    if len(devices) == 0:
                        ui.label(
                            "Es sind keine freien Geräte verfügbar. Erstelle zuerst ein neues Gerät.")

                        ui.button('Abbrechen', on_click=lambda: dialog.close()).props(
                            'flat')
                    else:
                        devices_options = {
                            device.id: device.name for device in devices}

                        ui.label(
                            "Wähle die Geräte aus, die dem Container zugeordnet werden sollen. Mehrfachauswahl möglich. Später können keine weiteren Geräte hinzugefügt werden.")
                        devices_input = ui.select(devices_options, multiple=True, label='Geräte auswählen').props(
                            'use-chips').classes('w-64')

                        with ui.stepper_navigation():
                            ui.button('Zurück', on_click=stepper.previous).props(
                                'flat')
                            ui.button('Erstellen', on_click=lambda: self.complete_container_creation(
                                dialog, name_input, description_input, location_input, devices_input))

    def check_container_name_input(self, stepper, name_input):
        if name_input.value == '':
            ui.notify('Bitte gib einen Namen für den Container an.',
                      type='warning')
            return

        stepper.next()

    def complete_container_creation(self, dialog, name_input, description_input, location_input, devices_input):
        if len(devices_input.value) == 0:
            ui.notify('Bitte wähle mindestens ein Gerät aus.',
                      type='warning')
            return

        self.create_container(name_input.value, description_input.value,
                              location_input.value, devices_input.value)
        dialog.close()

    def create_container(self, name, description, location, device_ids):
        if len(self.containers) == 0:
            self.cards_grid.clear()
            self.note_label.set_visibility(False)

        new_container = Container.add(
            name, description, location, device_ids)
        self.containers.append(new_container)
        with self.cards_grid:
            new_container_card = ContainerCard(wrapper=self.cards_grid, container=new_container, start_callback=self.start_container,
                                               stop_callback=self.stop_container, delete_callback=self.delete_container, live_view_callback=self.show_live_view_dialog)
            self.cards.append(new_container_card)
        self.update_stats()

    def start_container(self, container):
        container.start(self.iot_hub_helper)
        index = self.containers.index(container)
        self.cards[index].set_active()
        self.update_stats()

    def stop_container(self, container):
        container.stop()
        index = self.containers.index(container)
        self.cards[index].set_inactive()
        self.update_stats()

    def delete_container(self, container, dialog):
        if container.is_active:
            ui.notify(
                'Container ist aktiv und kann nicht gelöscht werden.', type='warning')
            return

        container.delete()

        index = self.containers.index(container)
        self.cards_grid.remove(self.cards[index].card)
        del self.containers[index]
        del self.cards[index]

        ui.notify(
            f"Container {container.name} erfolgreich gelöscht", type="positive")
        self.update_stats()
        dialog.close()

        if len(self.containers) == 0:
            self.show_note("Keine Container vorhanden")

    def show_live_view_dialog(self, container):
        self.live_view_dialog.show(container)
