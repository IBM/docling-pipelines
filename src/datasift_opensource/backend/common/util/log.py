# (C) Copyright IBM Corp. 2024.
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#  http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################

import logging
import os
import sys
import json

from common.util.constants import DatasiftConstants  #, Environments

HEALTH_API_SUFFIX = "/health"


class ConditionalFormatter(logging.Formatter): # pragma: no cover

    fields_to_be_included = [DatasiftConstants.JOB_ID, DatasiftConstants.JOB_RUN_ID, DatasiftConstants.TRACK_PERF]

    def format(self, record):
        from common.models.session_info import get_session_info
        session_info = get_session_info()
        log_dict = {
            "time": self.formatTime(record, self.datefmt),
            "logger": record.name,
            "logLevel": record.levelname,
            "transaction_ID": session_info.transaction_id,
            "message": record.getMessage() if record.getMessage() else record.msg,
            "saveServiceCopy": "false",
            "appname": "datasift-api"
        }

        # Include exc_info if it is present.
        if record.exc_info:
            log_dict.update({'exc_info': self.formatException(record.exc_info)})

        # Include stack_info if it is present.
        if record.stack_info:
            log_dict.update({'stack_info': record.stack_info})

        # check for optional field if present in the record dictionary then include in the log dictionary.
        for field in ConditionalFormatter.fields_to_be_included:
            if field in record.__dict__ and record.__dict__.get(field) is not None:
                log_dict.update({field: record.__dict__.get(field)})

        # if record level is debug then update the message.
        if record.levelno == logging.DEBUG:
            log_dict["message"] = f"{record.getMessage()} at {record.pathname}:{record.lineno}"

        # The below changes are specific for Local Environment.
        if 'exc_info' in log_dict:
            log_dict['exc_info'] = log_dict['exc_info'].splitlines()
        if 'stack_info' in log_dict:
            log_dict['stack_info'] = log_dict['stack_info'].splitlines()

        # if the record has exc_info or stack_info then indent the message so that the stack_info visible on console is in formatted option.
        if any(key in log_dict for key in ['exc_info', 'stack_info']):
            return json.dumps(log_dict, indent=2)

        return json.dumps(log_dict)


def get_log_level(name: str = None):
    """
    When log level is None or str
    :param name:
    :return:
    """
    if name is None:
        level_name = os.environ.get("DS_LOG_LEVEL", logging.INFO)
    else:
        level_name = name.upper()
    return level_name


def get_logger(name: str = DatasiftConstants.LOGGER_NAME,
               level: [int, str] = None,
               file: str = None,
               *,
               is_pg: bool = False,
               pg_params: dict = None) -> logging.Logger:
    """
    Returns a logger configured with stdout, file output, and optional Postgres handler.

    Args:
        name: Logger name.
        level: Log level string or int (e.g., "INFO" or logging.INFO).
        file: Optional file path for logs.
        is_pg: Enable Postgres logging if True.
        pg_params: Dict containing:
            {
                "project_id": str,
                "job_id": str,
                "job_run_id": str,
                "node_id": str,
                "name": str
            }

    Returns:
        logging.Logger
    """
    logger = logging.getLogger(name)

    # Set log level
    if isinstance(level, int):
        logger.setLevel(level)
    else:
        level = level.upper() if isinstance(level, str) else "INFO"
        logger.setLevel(logging.getLevelName(level))

    # Use JSON format only if explicitly enabled via environment variable
    use_json_format: bool = os.environ.get("DS_LOG_JSON", "False") == "True"
    
    # --- Console & file handlers (only add once) ---
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        timefmt = "%H:%M:%S"
        
        if use_json_format:
            # Use JSON format when explicitly enabled
            console_format = ConditionalFormatter(datefmt=timefmt)
        else:
            # Use normal logging format by default
            console_format = logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt=timefmt
            )
        
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

        # Optional file handler
        if file:
            file_handler = logging.FileHandler(file)
            
            if use_json_format:
                file_log_format = ConditionalFormatter(datefmt=timefmt)
            else:
                file_log_format = logging.Formatter(
                    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt=timefmt
                )
            
            file_handler.setFormatter(file_log_format)
            logger.addHandler(file_handler)

    logger.propagate = False
    return logger
