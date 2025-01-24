from tkinter import filedialog
from datetime import datetime
import xlsxwriter
import json
import csv


class ExportHelper:
    '''Helper class to export data to CSV, JSON or Excel file'''

    def save_to_file(self, data):
        '''Save data to file'''

        # Ask user to select file path
        filetypes = [("CSV", "*.csv"), ("JSON", "*.json"), ("Excel", "*.xlsx")]
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=filetypes)

        # Save data depending on file extension
        if file_path.endswith(".csv"):
            self._save_as_csv(file_path, data)
        elif file_path.endswith(".json"):
            self._save_as_json(file_path, data)
        elif file_path.endswith(".xlsx"):
            self._save_as_xlsx(file_path, data)

    def _save_as_json(self, file_path, data):
        '''Save data as JSON file'''
        with open(file_path, "w") as json_file:
            json.dump(data, json_file, indent=4,
                      default=self._datetime_to_string)

    def _save_as_csv(self, file_path, data):
        '''Save data as CSV file'''
        all_records = self._convert_data_dict_to_list(data)
        fieldnames = all_records[0].keys()

        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_records)

    def _save_as_xlsx(self, file_path, data):
        '''Save data as Excel file'''
        all_records = self._convert_data_dict_to_list(data)

        # Create a new workbook and add a worksheet
        workbook = xlsxwriter.Workbook(file_path)
        worksheet = workbook.add_worksheet()

        # Write the header row
        fieldnames = all_records[0].keys()
        for col, fieldname in enumerate(fieldnames):
            worksheet.write(0, col, fieldname)

        # Write the data rows
        for row, record in enumerate(all_records, start=1):
            for col, value in enumerate(record.values()):
                worksheet.write(row, col, value)

        # Close the workbook
        workbook.close()

    def _datetime_to_string(self, obj):
        '''Convert datetime object to string'''
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(
            f"Object of type '{type(obj)}' is not JSON serializable")

    def _convert_data_dict_to_list(self, data):
        '''Convert data dictionary to list'''
        all_records = []
        device_keys = data.keys()
        for device_key in device_keys:
            sensor_keys = data[device_key].keys()
            for sensor_key in sensor_keys:
                records = data[device_key][sensor_key]
                for record in records:
                    # Check if timestamp is datetime object
                    if isinstance(record["timestamp"], datetime):
                        record['timestamp'] = record["timestamp"].isoformat()
                    all_records.append(record)

        # sort all_records by timestamp
        all_records.sort(key=lambda record: record["timestamp"])
        return all_records
