from __future__ import annotations

import typing as t

from socratic.core import di

if t.TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource, ValueRange  # pyright: ignore [reportMissingModuleSource]


class GoogleSheetDictReader(object):
    """
    A class that provides a DictReader-like interface for Google Sheets.
    """

    _sheets: SheetsResource.SpreadsheetsResource
    _range: str
    _data: None | list[list[str]]
    _row_index: int
    _custom_fieldnames: list[str] | None

    spreadsheet_id: str
    sheet_name: str

    def __init__(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        fieldnames: list[str] | None = None,
        sheet_resource: SheetsResource.SpreadsheetsResource = di.Provide["vendor.google.sheets"],
    ):
        """
        Initialize the GoogleSheetDictReader.

        Args:
            spreadsheet_id: The ID of the Google Spreadsheet
            sheet_name: The name of the sheet within the spreadsheet
            fieldnames: Optional list of field names. If not provided, the first row will be used
            sheet_resource: An authenticated Google Sheets API resource
        """
        self.sheet_resource = sheet_resource
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self._range = f"{sheet_name}"
        self._data = None
        self._row_index = 0
        self._custom_fieldnames = fieldnames
        self.fieldnames = self._get_fieldnames()

    def _get_sheet_data(self) -> list[list[str]]:
        """Fetch all data from the sheet."""
        if self._data is None:
            result = self.sheet_resource.values().get(spreadsheetId=self.spreadsheet_id, range=self._range).execute()
            self._data = result.get("values", [])
        return self._data

    def _get_fieldnames(self) -> list[str]:
        """Get field names from the first row or use provided fieldnames."""
        data = self._get_sheet_data()
        if not data:
            return []

        if self._custom_fieldnames:
            return self._custom_fieldnames

        # Use first row as fieldnames and convert to strings
        return [str(field) for field in data[0]]

    def __iter__(self) -> GoogleSheetDictReader:
        """Reset iterator to beginning."""
        self._row_index = 1  # Start from second row (after header)
        return self

    def __next__(self) -> dict[str, str]:
        """Return the next row as a dict."""
        data = self._get_sheet_data()
        if self._row_index >= len(data):
            raise StopIteration

        row = data[self._row_index]
        self._row_index += 1

        # Create a dict for the row, handling potential mismatches in column count
        row_dict: dict[str, str] = {}
        for i, field in enumerate(self.fieldnames):
            if i < len(row):
                row_dict[field] = row[i]
            else:
                row_dict[field] = ""

        return row_dict


class GoogleSheetDictWriter(object):
    """
    A class that provides a DictWriter-like interface for Google Sheets.
    """

    _sheets: SheetsResource.SpreadsheetsResource
    _next_row: int

    spreadsheet_id: str
    sheet_name: str
    fieldnames: list[str]

    def __init__(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        fieldnames: list[str],
        write_header: bool = False,
        sheets: SheetsResource.SpreadsheetsResource = di.Provide["vendor.google.sheets"],
    ):
        """
        Initialize the GoogleSheetDictWriter.

        Args:
            spreadsheet_id: The ID of the Google Spreadsheet
            sheet_name: The name of the sheet within the spreadsheet
            fieldnames: List of field names for the spreadsheet
            write_header: Whether to write the header row
            sheet_resource: An authenticated Google Sheets API resource
        """
        self._sheets = sheets
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.fieldnames = fieldnames
        self._next_row = 1  # Start at row 1 (row 0 is for header)

        # Write header if requested
        if write_header:
            self.writeheader()

    def _get_next_row_index(self) -> int:
        """
        Get the index of the next empty row.
        """
        range_name = f"{self.sheet_name}!A:A"  # Just need the first column
        result = self._sheets.values().get(spreadsheetId=self.spreadsheet_id, range=range_name).execute()

        values = result.get("values", [])
        return len(values) + 1  # Return the next available row index

    @staticmethod
    def _col_num_to_letter(n: int) -> str:
        """
        Convert a column number to a column letter reference (A, B, ..., Z, AA, AB, etc.)

        Args:
            n: 0-based column index

        Returns:
            Column letter reference (A-based)
        """
        if n < 0:
            raise ValueError("Column index cannot be negative")

        result = ""
        while True:
            n, remainder = divmod(n, 26)
            result = chr(65 + remainder) + result
            if n == 0:
                break
            n -= 1  # Adjust for 1-based indexing in Excel's column naming

        return result

    def _get_column_range(self, start_col: int, end_col: int) -> tuple[str, str]:
        """
        Get column letters for a range.

        Args:
            start_col: 0-based starting column index
            end_col: 0-based ending column index (inclusive)

        Returns:
            Tuple of (start_column_letter, end_column_letter)
        """
        start_letter = self._col_num_to_letter(start_col)
        end_letter = self._col_num_to_letter(end_col)
        return start_letter, end_letter

    def _get_range_reference(self, start_row: int, end_row: int, start_col: int, end_col: int) -> str:
        """
        Get a full range reference in A1 notation (e.g., 'Sheet1!A1:C10').

        Args:
            start_row: 1-based starting row index
            end_row: 1-based ending row index
            start_col: 0-based starting column index
            end_col: 0-based ending column index

        Returns:
            Range reference in A1 notation including sheet name
        """
        start_col_letter, end_col_letter = self._get_column_range(start_col, end_col)
        return f"{self.sheet_name}!{start_col_letter}{start_row}:{end_col_letter}{end_row}"

    def writeheader(self) -> None:
        """Write the header row to the sheet."""
        last_col = len(self.fieldnames) - 1
        range_name = self._get_range_reference(1, 1, 0, last_col)

        body: ValueRange = {"values": [self.fieldnames]}
        self._sheets.values().update(
            spreadsheetId=self.spreadsheet_id, range=range_name, valueInputOption="RAW", body=body
        ).execute()
        self._next_row = 2  # Next row is now 2

    def encode_value(self, v: t.Any) -> t.Any:
        match v:
            case None:
                return None
            case bool() | int():
                return v
            case list() | tuple():
                return ":".join(self.encode_value(u) for u in t.cast(t.Sequence[t.Any], v))
            case _:
                return str(v)

    def writerow(self, row_dict: dict[str, t.Any]) -> None:
        """
        Write a single row to the sheet.

        Args:
            row_dict: Dictionary mapping field names to values
        """
        # Always get the latest next row index
        self._next_row = self._get_next_row_index()

        # Convert dict to row based on fieldnames
        row_values = []
        for field in self.fieldnames:
            row_values.append(self.encode_value(row_dict.get(field, "")))

        last_col = len(self.fieldnames) - 1
        start_col, end_col = self._get_column_range(0, last_col)
        range_name = f"{self.sheet_name}!{start_col}{self._next_row}:{end_col}{self._next_row}"
        body: ValueRange = {"values": [row_values]}

        self._sheets.values().update(
            spreadsheetId=self.spreadsheet_id, range=range_name, valueInputOption="RAW", body=body
        ).execute()

    def writerows(self, row_dicts: t.Sequence[dict[str, t.Any]]) -> None:
        """
        Write multiple rows to the sheet.

        Args:
            row_dicts: List of dictionaries, each mapping field names to values
        """
        if not row_dicts:
            return

        # Always get the latest next row index
        self._next_row = self._get_next_row_index()

        # Convert dicts to rows based on fieldnames
        all_values = []
        for row_dict in row_dicts:
            row_values = []
            for field in self.fieldnames:
                row_values.append(self.encode_value(row_dict.get(field, "")))
            all_values.append(row_values)

        # Calculate the range for all rows
        last_row = self._next_row + len(row_dicts) - 1
        last_col = len(self.fieldnames) - 1
        range_name = self._get_range_reference(self._next_row, last_row, 0, last_col)

        body: ValueRange = {"values": all_values}

        self._sheets.values().update(
            spreadsheetId=self.spreadsheet_id, range=range_name, valueInputOption="RAW", body=body
        ).execute()

    def clear(self) -> None:
        """
        Clear the entire sheet content, including headers.
        """
        # Clear the sheet by specifying the entire sheet range
        range_name = f"{self.sheet_name}"

        self._sheets.values().clear(spreadsheetId=self.spreadsheet_id, range=range_name, body={}).execute()

        # Reset the next row tracker
        self._next_row = 1
