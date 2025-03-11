import os
import logging
from config import CACHE_DIR
import time
import json
from typing import Dict, Any
import threading
from datetime import datetime, timedelta

file_lock = threading.Lock()

logger = logging.getLogger(__name__)
# Path for the cache file
CACHE_FILE = "meraki_network_cache.json"
CACHE_EXPIRATION = 7 * 24 * 60 * 60  # 7 days in seconds

def setup_logging(min_log_level=logging.INFO):
    """
    Sets up logging to separate files for each log level.
    Only logs from the specified `min_log_level` and above are saved in their respective files.
    Includes console logging for the same log levels.

    :param min_log_level: Minimum log level to log. Defaults to logging.INFO.
    """
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    if not os.access(logs_dir, os.W_OK):
        raise PermissionError(f"Cannot write to log directory: {logs_dir}")

    # Log files for each level
    log_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    # Create the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture all log levels
    # Define a log format
    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Set up file handlers for each log level
    for level_name, level_value in log_levels.items():
        if level_value >= min_log_level:
            log_file = os.path.join(logs_dir, f"{level_name.lower()}.log")
            handler = logging.FileHandler(log_file)
            handler.setLevel(level_value)
            handler.setFormatter(log_format)

            # Add a filter so only logs of this specific level are captured
            handler.addFilter(lambda record, lv=level_value: record.levelno == lv)
            logger.addHandler(handler)

    # Set up console handler for logs at `min_log_level` and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(min_log_level)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    logging.info(f"Logging is set up. Minimum log level: {logging.getLevelName(min_log_level)}")

    # Configure the 'meraki' logger separately

    logging.getLogger('meraki').disabled = True


def fetch_meraki_networks(dashboard, org_id: str) -> Dict[str, str]:
    """
    Fetch Meraki networks and cache them if needed.
    If the cache is valid, load data from the cache.
    Otherwise, fetch data from the API and update the cache.

    :param dashboard: Meraki Dashboard API instance
    :param org_id: Meraki organization ID
    :return: A dictionary of network names to network IDs
    """
    # Check if the cache exists and is valid
    cache_path = os.path.join(CACHE_DIR, CACHE_FILE)
    if os.path.exists(cache_path):
        with open(cache_path, "r") as cache_file:
            cache_data = json.load(cache_file)

            # Check if the cache is still valid
            if "timestamp" in cache_data:
                age = time.time() - cache_data["timestamp"]
                if age < CACHE_EXPIRATION:
                    # Return cached data
                    return cache_data["data"]

    # Fetch data from the Meraki API if cache is invalid or doesn't exist
    meraki_networks = dashboard.organizations.getOrganizationNetworks(org_id)
    if meraki_networks:
        logger.debug('Retrieved Meraki networks')
    else:
        logger.error('No Meraki networks found')

    # Convert to `network_names: network_id` structure
    network_data = {network["name"]: network["id"] for network in meraki_networks}

    # Update the cache
    with open(cache_path, "w") as cache_file:
        json.dump({
            "timestamp": time.time(),
            "data": network_data
        }, cache_file)

    return network_data


def invalidate_network_cache():
    """
    Invalidate the Meraki network cache by removing the cache file.
    """
    cache_path = os.path.join(CACHE_DIR, CACHE_FILE)
    if os.path.exists(cache_path):
        os.remove(cache_path)
        logger.debug(f"Cache invalidated: {cache_path}")
    else:
        logger.debug("No cache found to invalidate.")

def get_meraki_network_id(name: str, meraki_networks: Dict[str, str]) -> str:
    """
    Retrieves the network ID for a given network name from a dictionary of Meraki networks.

    This function iterates through the provided dictionary of Meraki networks, where the keys
    are the network names, and the values are their corresponding network IDs. It matches the
    provided network name with the keys in the dictionary and returns the associated network ID
    if a match is found.

    :param name: The name of the network for which the ID is to be retrieved.
    :type name: str
    :param meraki_networks: A dictionary mapping network names to their respective network IDs.
    :type meraki_networks: Dict[str, str]
    :return: The network ID corresponding to the given network name.
    :rtype: str
    """
    for network_name, network_id in meraki_networks.items():
        if network_name == name:
            return network_id

def backup(backup_dir: str, network_name: str, endpoint: str, data: Dict[str, Any]):
    """
    Backs up the configuration data for the specified network name and endpoint in a
    structured JSON format:
        network_name -> endpoint -> timestamp -> data
    Ensures backups are categorized by timestamp and automatically cleans up old backups
    (older than ~4 months).

    :param backup_dir: The directory path where backup files will be stored.
    :type backup_dir: str
    :param network_name: The name of the network whose configuration is being backed up.
    :type network_name: str
    :param endpoint: The name of the endpoint for which the backup is being created.
    :type endpoint: str
    :param data: A dictionary containing the configuration data to be backed up.
    :type data: Dict[str, Any]

    :return: None
    """
    # Ensure the backup directory exists
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        logger.info(f"Backup directory created: {backup_dir}")

    # Generate timestamp
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

    # Backup file path
    backup_file_path = os.path.join(backup_dir, f"{network_name}.json")

    # Load existing backup data if it exists
    backup_data = {}
    if os.path.exists(backup_file_path):
        try:
            with open(backup_file_path, "r") as f:
                backup_data = json.load(f)  # Load existing backup
        except json.JSONDecodeError:
            logger.warning(f"Backup file {backup_file_path} is corrupted. A new backup will be created.")
            backup_data = {}

    # Ensure the structure matches: network_name -> endpoint -> timestamp -> data
    if network_name not in backup_data:
        backup_data[network_name] = {}

    if endpoint not in backup_data[network_name]:
        backup_data[network_name][endpoint] = {}

    # Add the new backup under the current timestamp
    backup_data[network_name][endpoint][timestamp] = data

    # Write back the updated backup data to the file
    with file_lock:
        with open(backup_file_path, "w") as f:
            json.dump(backup_data, f, indent=4)
            logger.info(f"Configuration backed up for site '{network_name}' at endpoint '{endpoint}'.")

    # Clean up old backups (older than 4 months) for this endpoint
    cutoff_date = now - timedelta(days=4 * 30)  # Approximate 4 months as 120 days

    for endpoint_name in backup_data[network_name]:
        timestamps_to_delete = []
        for date_str in list(backup_data[network_name][endpoint_name].keys()):
            try:
                backup_date = datetime.strptime(date_str, "%Y-%m-%d_%H-%M-%S")
                if backup_date < cutoff_date:
                    timestamps_to_delete.append(date_str)
                    logger.info(f"Old backup {date_str} for '{endpoint_name}' scheduled for deletion.")
            except ValueError:
                logger.warning(f"Invalid timestamp format found in {backup_file_path}: {date_str}")

        # Remove the old timestamps
        for timestamp_to_delete in timestamps_to_delete:
            del backup_data[network_name][endpoint_name][timestamp_to_delete]

    # Save cleaned data back to the backup file
    with file_lock:
        with open(backup_file_path, "w") as f:
            json.dump(backup_data, f, indent=4)