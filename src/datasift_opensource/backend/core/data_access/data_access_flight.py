# (C) Copyright IBM Corp. 2024.
from typing import Any

import pyarrow as pa
import pyarrow.flight
from data_processing.data_access import DataAccess
from data_processing.utils import TransformUtils

from common.util.constants import DatasiftConstants
from common.util.log import get_logger

logger = get_logger()


class DataAccessFlight(DataAccess):
    """
    Implementation of the Data access flight for flight server data access
    """

    def __init__(self, flight_config: dict[str, str] = None, checkpoint: bool = False):
        """
        Create data access class for flight configuration
        """
        url = flight_config["url"]
        self.flight_client = pa.flight.connect(url)
        logger.info("Connected to Flight server at %s", url)
        self.output_folder = TransformUtils.clean_path(flight_config[DatasiftConstants.OUTPUT_FOLDER])
        self.checkpoint = checkpoint
        self.tables = {}

        logger.debug(f"URL: {url}")
        logger.debug(f"Local output folder: {self.output_folder}")
        logger.debug(f"Checkpoint: {self.checkpoint}")

    def get_output_folder(self) -> str:
        """
        Get output folder as a string
        :return: output_folder
        """
        return self.output_folder

    def get_table(self, path: str) -> pa.table:
        """
        Attempts to read a PyArrow table from the given path.

        Args:
            path (str): Path to the file containing the table.

        Returns:
            pyarrow.Table: PyArrow table if read successfully, None otherwise.
        """
        try:
            logger.debug("Path: %s", path)

            # if the table exists in memory, use it for faster access
            if self.tables.get(path):
                logger.debug("Table found in memory")
                return self.tables[path], 0

            descriptor = pa.flight.FlightDescriptor.for_path(path=path)
            info = self.flight_client.get_flight_info(descriptor)

            reader = self.flight_client.do_get(info.endpoints[0].ticket)
            return pa.Table.from_pandas(reader.read_pandas()), 0

        except (OSError, FileNotFoundError, pa.ArrowException) as e:
            logger.error(f"Error reading table from {path}: {e}")
            return None

    def get_all_tables(self):
        flights_gen = self.flight_client.list_flights()
        return flights_gen

    def save_table(self, path: str, table: pa.Table) -> tuple[int, dict[str, Any]]:
        """
        Save the given parquet table and return information

        Args:
            path (str): The path to the output file.

        Returns:
            tuple: A tuple containing:
                - size_in_memory (int): The size of the table in memory (bytes).
                - file_info (dict or None): A dictionary containing:
                    - name (str): The name of the file.
                    - size (int): The size of the file (bytes).
                If saving fails, file_info will be None.
        """
        logger.debug("Path: %s", path)

        # save the table in memory for faster access
        self.tables[path] = table

        writer, _ = self.flight_client.do_put(pa.flight.FlightDescriptor.for_path(path=path), table.schema)
        writer.write_table(table)
        writer.close()

        return table.nbytes, {}


def main():  # pragma: no cover
    # run the server first:
    # python3 src/utils/flight_server.py

    # create data access instance
    url = "grpc+tcp://localhost:5005"
    data_access = DataAccessFlight(url)

    # save a table to the flight server, using the pathname as a key
    _, data_table = data_access.save_table("example.parquet")
    print(data_table.to_pandas().keys())

    # get the sample table from the flight sever, pathname is the key
    df = data_access.get_table("example.parquet")
    print(df.keys())

    # flight list is a generator containing all tables in the server
    flight_list = data_access.get_all_tables()

    for flight in flight_list:
        # print(flight.descriptor)
        descriptor = flight.descriptor.path[0]
        key = descriptor.decode("utf-8")
        print(key)


# main entry point into the program;
if __name__ == "__main__":  # pragma: no cover
    main()
