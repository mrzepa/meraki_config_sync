import logging
import json
import os
import csv
import meraki
from icecream import ic
import ipaddress
from dotenv import load_dotenv
from utils import setup_logging, fetch_meraki_networks, invalidate_network_cache, get_meraki_network_id, backup
from typing import Dict, Any, Optional, Tuple, List
import config
import argparse

logger = logging.getLogger(__name__)

env_path = os.path.join(os.path.expanduser("~"), ".env")
load_dotenv()

def vlan_missing_report(meraki_networks: dict, standard_vlans: dict) -> dict:
    """
    Generates a VLAN missing and mismatch report for given Meraki networks. The function
    compares the VLANs configured in the Meraki networks with a predefined list of standard
    VLANs, identifying any missing VLANs or mismatched VLAN IDs. Results are written to
    a JSON file in the specified output directory.

    :param meraki_networks: A list of dictionaries representing Meraki networks. Each dictionary
        should contain at least the keys 'id' and 'name'.
    :param standard_vlans: A dictionary where the keys are VLAN names and the values are another dict with the vlan 'ID' key.
    :return: None
    """
    # Initialize report container
    vlan_report = {}

    for network_name, network_id in meraki_networks.items():
        # Retrieve VLANs from the Meraki MX device
        try:
            mx_vlans = dashboard.appliance.getNetworkApplianceVlans(network_id)
        except meraki.exceptions.APIError as e:
            if "VLANs are not enabled for this network" in e.message:
                logger.debug(f'No vlans on {network_name}')
                vlan_report[network_name] = {
                    "missing_vlans": [],
                    "mismatched_vlans": [],
                    "error": "VLANs not enabled"
                }

                continue
        # Convert Meraki MX VLANs into a lookup dictionary
        mx_vlan_lookup = {vlan['name']: vlan['id'] for vlan in mx_vlans}

        # Check for missing VLANs and mismatches
        missing_vlans = []
        mismatched_vlans = []

        for vlan_name, vlan_data in standard_vlans.items():
            expected_id = vlan_data.get("ID")  # Extract the VLAN ID from the inner dict
            if vlan_name not in mx_vlan_lookup:
                missing_vlans.append(vlan_name)  # VLAN is missing
            else:
                mx_vlan_id = mx_vlan_lookup[vlan_name]
                if mx_vlan_id != expected_id:
                    # VLAN ID does not match
                    mismatched_vlans.append({
                        "name": vlan_name,
                        "expected_id": expected_id,
                        "actual_id": mx_vlan_id
                    })

        # Add results to the report for the current network
        vlan_report[network_name] = {
            "missing_vlans": missing_vlans,
            "mismatched_vlans": mismatched_vlans
        }
    filename = 'vlan_report.json'
    file_path = os.path.join(config.OUTPUT_DIR, filename)
    with open(file_path, 'w') as f:
        json.dump(vlan_report, f, indent=4)

    return vlan_report

def build_combined_data(site_dict: dict, standard_vlans: dict) -> dict:
    """
    Builds a nested dictionary that combines VLAN data from `site_dict` with details
    from `standard_vlans`. It organizes VLAN data per site, including information about
    network prefixes, VLAN IDs, and VPN modes.

    :param site_dict: A dictionary where the keys are site names and the values are
        dictionaries mapping VLAN names to subnet information.
    :param standard_vlans: A dictionary where the keys are VLAN names and the values
        are dictionaries containing additional details for each VLAN such as its ID
        and VPN mode.
    :return: A nested dictionary where each key is a site name, and each value is
        another dictionary mapping VLAN names to combined data, including subnet prefixes,
        VLAN IDs, and VPN modes.
    :rtype: dict
    """
    combined_data = {}

    for site_name, vlan_data in site_dict.items():
        combined_data[site_name] = {}

        for vlan_name, subnet in vlan_data.items():
            # Combine subnet from site_dict and details from standard_vlans
            vlan_details = standard_vlans.get(vlan_name, {})  # Get matching VLAN details or empty dict
            combined_data[site_name][vlan_name] = {
                "Prefix": subnet.strip(),  # Include the subnet (strip leading/trailing whitespace)
                "ID": vlan_details.get("ID", None),  # Get the ID or None if not present
                "VPN Mode": vlan_details.get("VPN Mode", None),  # Get VPN Mode or None if not present
                "DHCP Server": vlan_details.get("DHCP Server", True)  # DCHP Server for this vlan?
            }

    return combined_data

def meraki_vlans(site_data: dict, network_name: str, network_id: str, add_missing: bool = False,
                 update_existing: bool = False):
    """
    Add or update Meraki VLANs for a given network in the Meraki dashboard.

    :param site_data: A dictionary containing VLAN data for multiple sites.
    :type site_data: dict
    :param network_name: The name of the network in the input site data.
    :type network_name: str
    :param network_id: The unique identifier of the network in the Meraki dashboard.
    :type network_id: str
    :param add_missing: If True, adds missing VLANs that exist in the site_data but not in Meraki.
    :type add_missing: bool
    :param update_existing: If True, updates existing VLANs in Meraki using the details in site_data.
    :type update_existing: bool
    :return: None. Performs VLAN additions and/or updates on the network and logs progress.
    :rtype: None
    """

    def add_dhcp_server(network_id, vlan_name, vlan_id, network_name):
        meraki_api_payload = {}
        file_path = os.path.join(config.INPUT_DIR, 'sites', network_name, vlan_name)
        dhcp_setting_filename = 'dhcp.json'
        fixed_filename = 'fixed.csv'
        reserved_filename = 'reserved.csv'
        dhcp_setting_path = os.path.join(file_path, dhcp_setting_filename)
        fixed_path = os.path.join(file_path, fixed_filename)
        reserved_path = os.path.join(file_path, reserved_filename)

        # Check if dhcp.json exists (required file)
        if os.path.exists(dhcp_setting_path):
            try:
                with open(dhcp_setting_path, 'r') as dhcp_file:
                    dhcp_settings = json.load(dhcp_file)
                meraki_api_payload.update(dhcp_settings)
                logger.info(f"Loaded DHCP settings from {dhcp_setting_path}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in DHCP settings file {dhcp_setting_path}: {e}")

            # Check optional fixed.csv file
            if os.path.exists(fixed_path):
                try:
                    with open(fixed_path, 'r') as fixed_file:
                        fixed_reader = csv.DictReader(fixed_file)
                        fixed_assignments = {}
                        for row in fixed_reader:
                            mac_address = row['MAC address'].strip()
                            fixed_assignments[mac_address] = {
                                'ip': row['LAN IP'].strip(),
                                'name': row['Client name'].strip()
                            }

                    meraki_api_payload["fixedIpAssignments"] = fixed_assignments
                    logger.info(f"Loaded fixed IP assignments from {fixed_path}")
                except Exception as e:
                    logger.exception(f"Error reading fixed IP file {fixed_path}: {e}")
            else:
                logger.info(f"{fixed_path} not found. Skipping fixed IP assignments.")

            # Check optional reserved.csv file
            if os.path.exists(reserved_path):
                try:
                    with open(reserved_path, 'r') as reserved_file:
                        reserved_reader = csv.DictReader(reserved_file)
                        reserved_ranges = []  # Initialize an empty list
                        for row in reserved_reader:
                            reserved_ranges.append({
                                'start': row['First IP'].strip(),
                                'end': row['Last IP'].strip(),
                                'comment': row['Comment'].strip()
                            })

                    meraki_api_payload["reservedIpRanges"] = reserved_ranges
                    logger.info(f"Loaded reserved IP ranges from {reserved_path}")
                except Exception as e:
                    logger.error(f"Error reading reserved IP file {reserved_path}: {e}")
            else:
                logger.info(f"{reserved_path} not found. Skipping reserved IP ranges.")

            dashboard.appliance.updateNetworkApplianceVlan(networkId=network_id, vlanId=vlan_id,
                                                           **meraki_api_payload)
            logger.info(f"Successfully added DHCP settings to VLAN {vlan_name} in site {network_name}")
        else:
            logger.warning(f"{dhcp_setting_path} not found. Skipped adding DHCP settings.")

    # Validate input: At least one of add_missing or update_existing must be True
    if not add_missing and not update_existing:
        logger.error("At least one of 'add_missing' or 'update_existing' must be True.")
        return

    # Prepare missing VLANs and update VLANs
    missing_vlans = {}
    vlans_to_update = {}

    for site_name, vlan_data in site_data.items():
        if site_name == network_name:
            # Filter VLANs with a defined "Prefix" (non-empty "Subnet")
            vlans_with_prefix = {
                vlan_name: details for vlan_name, details in vlan_data.items() if details.get("Prefix")
            }

            # Retrieve existing Meraki VLANs
            existing_meraki_vlans = dashboard.appliance.getNetworkApplianceVlans(network_id)
            existing_vlan_names = {vlan["name"]: vlan for vlan in
                                   existing_meraki_vlans}  # Map name to full VLAN details for update

            # Compare input VLANs with existing Meraki VLANs
            for vlan_name, details in vlans_with_prefix.items():
                try:
                    ipaddress.ip_interface(details["Prefix"])  # Validate IP prefix
                except ValueError as e:
                    raise ValueError(
                        f'{details["Prefix"]} is not a valid IP address prefix for site {network_name}.')

                if vlan_name not in existing_vlan_names:
                    # Missing VLAN - Prepare to add
                    if add_missing:
                        missing_vlans[vlan_name] = details
                else:
                    # Existing VLAN - Prepare to update
                    if update_existing:
                        vlans_to_update[vlan_name] = details

            break  # Process only the specific network_name

    # Handle Missing VLANs (Add them)
    if add_missing and missing_vlans:
        logger.info(f"Adding missing VLANs to {network_name}: {missing_vlans}")
        for vlan_name, vlan_details in missing_vlans.items():
            # Construct payload for the Meraki API
            meraki_api_payload = {
                "id": vlan_details["ID"],
                "name": vlan_name,
                "subnet": vlan_details["Prefix"],
                "applianceIp": vlan_details["Prefix"].split('/')[0],  # Extract appliance IP from Prefix
                "vpnMode": vlan_details["VPN Mode"],
                "ipv6": {'enabled': True}
            }

            try:
                # Create the VLAN in Meraki
                dashboard.appliance.createNetworkApplianceVlan(networkId=network_id, **meraki_api_payload)
                # Log success
                logger.info(f"Successfully added VLAN {vlan_name} to network {network_name}: {meraki_api_payload}")
            except Exception as e:
                # Log failure
                logger.error(f"Failed to add VLAN {vlan_name} to network {network_name}: {e}")

            if vlan_details["DHCP Server"]:
                add_dhcp_server(network_id, vlan_name, vlan_details["ID"], network_name)


    # Handle Existing VLANs (Update them)
    if update_existing and vlans_to_update:
        logger.info(f"Updating existing VLANs in {network_name}: {vlans_to_update}")
        for vlan_name, vlan_details in vlans_to_update.items():
            # Backup before making changes
            try:
                vlan_to_backup = dashboard.appliance.getNetworkApplianceVlan(meraki_network_id,
                                                                             vlanId=vlan_details["ID"])
                backup(config.BACKUP_DIR, network_name, f'vlan_{vlan_details["ID"]}', vlan_to_backup)
            except Exception as e:
                logger.error(f"Failed to backup VLAN {vlan_name} in network {network_name}: {e}")
                continue

            # Construct payload for updating VLAN
            meraki_api_payload = {
                "id": vlan_details["ID"],
                "name": vlan_name,
                "subnet": vlan_details["Prefix"],
                "applianceIp": vlan_details["Prefix"].split('/')[0],
                "vpnMode": vlan_details["VPN Mode"],
                "ipv6": {'enabled': True}
            }
            try:
                # Update the VLAN in Meraki
                dashboard.appliance.updateNetworkApplianceVlan(networkId=network_id, vlanId=vlan_details["ID"],
                                                               **meraki_api_payload)
                # Log success
                logger.info(f"Successfully updated VLAN {vlan_name} in network {network_name}: {meraki_api_payload}")
            except Exception as e:
                # Log failure
                logger.error(f"Failed to update VLAN {vlan_name} in network {network_name}: {e}")

            if vlan_details["DHCP Server"]:
                add_dhcp_server(network_id, vlan_name, vlan_details["ID"], network_name)
def update_meraki_ports(data_list: dict, network_name: str, network_id: str, standard_vlans: dict):
    """
    Updates Meraki ports based on the provided data list, only for the given network name and ID.

    :param data_list: A list of dictionaries where each dictionary represents a row of port data.
                     Keys are the column headers (e.g., site_name, port_number, port_type, vlan, secure).
    :param network_name: The name of the network for which ports need to be updated.
    :param network_id: The ID of the Meraki network for which ports need to be updated.
    :param standard_vlans: A dictionary containing VLAN definitions, where each key is a VLAN name
                          and each value is a dictionary with VLAN properties (e.g., ID, VPN Mode).
    :return: None
    """

    # Extract all valid VLAN IDs from the standard_vlans dictionary
    valid_vlan_ids = {vlan_data["ID"] for vlan_data in standard_vlans.values()}

    for row in data_list:
        site_name = row.get("site_name")
        port_number = str(row.get("number"))
        port_type = row.get("type")
        port_vlan = int(row.get("vlan"))
        port_security = row.get("secure")

        if not all([site_name, port_number, port_type, port_vlan]):
            logger.warning(f"Incomplete row data: {row} for {network_name}. Exiting")
            raise ValueError(f'Missing port data at {network_name}. Each row needs to have site_name, number, type, and vlan.')

        if port_type not in ["access", "trunk"]:
            logger.warning(f'Port type must be one of access or trunk. Exiting.')
            raise ValueError(f'Incorect port type for {site_name}. Value provided was {port_type}.')

        # Validate VLAN and check if it exists in the list of valid VLAN IDs
        try:
            if port_vlan not in valid_vlan_ids:
                logger.warning(
                    f"VLAN {port_vlan} for port {port_number} at site {site_name} is not in the standard VLANs. Exiting.")
                raise ValueError(f'Incorect VLAN for port {port_number} at {site_name}. Value provided was {port_vlan}.')
        except ValueError:
            raise ValueError(f'Incorect VLAN for port {port_number} at {site_name}. Value provided was {port_vlan}.')

        if port_security.lower() not in ["y", "n"]:
            logger.warning(f'Port security must be one of y or n. Exiting.')
            raise ValueError(f'Incorect port security for {site_name}. Value provided was {port_security}.')

        if port_security.lower() == "y":
            accessPolicy = 'hybrid-radius'
        else:
            accessPolicy = 'open'

        port_payload = {'number': port_number,
                        'type': port_type,
                        'enabled': True,
                        'vlan': port_vlan,
                        }
        if port_type == "access":
            port_payload['accessPolicy'] = accessPolicy
        if port_type == "trunk":
            port_payload['allowedVlans'] = 'all'
            port_payload['dropUntaggedTraffic'] = False

        # make sure we are dealing with the correct site information by matching the site_name to the network_name
        # provided.
        if site_name == network_name:
            try:
                # before making any changes to a port, backup it's existing configuration
                existing_meraki_port = dashboard.appliance.getNetworkAppliancePort(network_id, portId=port_number)
                backup(config.BACKUP_DIR, network_name, f'port_{port_number}', existing_meraki_port)
                new_meraki_port = dashboard.appliance.updateNetworkAppliancePort(network_id, portId=port_number, **port_payload)
                if new_meraki_port:
                    logger.info(f'Updated port {port_number} at site {network_name} with payload: {new_meraki_port}')
            except Exception as e:
                logger.error(f"Failed to update port {port_number} at site {network_name}: {e}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description=f"Meraki Site Sync")

    site_name_group = parser.add_mutually_exclusive_group(required=True)

    # Add the verbose flag
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output (debug level logging)"
    )

    parser.add_argument(
        "--vlans",
        type=str,
        help=f"Add/Update VLANs at Meraki Site. Filename containing the vlans and prefixes in csv format located in {config.INPUT_DIR}. Must be used with --a or --u."
    )
    parser.add_argument(
        "-a",
        action="store_true",
        help=f"Add VLANs that are missing at Meraki Site. Must be used with --vlans"
    )
    parser.add_argument(
        "-u",
        action="store_true",
        help=f"Update VLANs at Meraki Site. Must be used with --vlans"
    )
    parser.add_argument(
        "--vlans-report",
        action="store_true",
        help="Generate VLANs missing and missmatched report for all Meraki networks."
    )
    parser.add_argument(
        "--ports",
        type=str,
        help="Update Ports at Meraki Site. Filename containing the ports and security role in csv format."
    )
    site_name_group.add_argument(
        "--site-name",
        nargs=1,
        help="Name of the site to apply the changes to."
    )
    site_name_group.add_argument(
        "--site-names-file",
        type=str,
        help='File containing a list of site names to apply changes to.'
    )
    parser.add_argument(
        "-m", "--multi-site",
        action="store_true",
        help="Apply changes to multiple sites at once."
    )

    # Parse the arguments
    args = parser.parse_args()

    # Set up logging based on the verbose flag
    if args.verbose:
        setup_logging(logging.DEBUG)
    else:
        setup_logging(logging.INFO)

    try:
        MERAKI_API_KEY: str = os.getenv('MERAKI_API_KEY')
        MERAKI_ORG_ID: str = os.getenv('MERAKI_ORG_ID')
    except KeyError as e:
        logger.critical(f'Missing Meraki api_key and org_id environment variables. {e}')
        raise SystemExit(1)

    # Initialize the Meraki dashboard API
    dashboard = meraki.DashboardAPI(MERAKI_API_KEY, output_log=False)
    if dashboard:
        logger.info('Connected to Meraki dashboard')
    else:
        logger.critical('No Meraki dashboard found')
        raise SystemExit(1)

    # Get the list of standard vlans
    standard_vlans_filename = 'vlans.json'
    standard_vlans_path = os.path.join(config.INPUT_DIR, standard_vlans_filename)
    with open(standard_vlans_path, 'r') as f:
        standard_vlans = json.load(f)

    # Get the list of meraki network IDs
    meraki_networks = fetch_meraki_networks(dashboard, MERAKI_ORG_ID)

    # Get the site name(s) to apply changes too
    if args.site_name:
        meraki_network_names = args.site_name
    elif args.site_names_file:
        meraki_network_name_filename = args.site_names_file
        meraki_network_name_path = os.path.join(config.INPUT_DIR, meraki_network_name_filename)
        with open(meraki_network_name_path, 'r') as f:
            meraki_network_names = [line.strip() for line in f if line.strip()]
    else:
        logger.error('Missing site name. Please use --site-name [site_name] or --site-names-file [filename.txt].')
        raise SystemExit(1)

    if args.vlans:
        if not args.vlans:
            logger.error('Missing vlans file. Please use --vlans filename.csv')
            raise SystemExit(1)

        if not args.a and not args.u:
            logger.error('Missing --a or --u flag. Please use --a or --u flag.')
            raise SystemExit(1)

        if args.multi_site:
            # Multi-site updates can't deal with dhcp settings. This will just add the prefixes
            filename = args.vlans
            site_prefixes_path = os.path.join(config.INPUT_DIR, filename)
            with open(site_prefixes_path, 'r') as f:
                csv_reader = csv.DictReader(f)
                # Use the first column (site_name) as the key, excluding it from the sub-dictionary
                site_dict = {
                    row[csv_reader.fieldnames[0]]: {key: value for key, value in row.items() if key != csv_reader.fieldnames[0]}
                    for row in csv_reader
                }
        else:
            filename = 'subnets.csv'
            file_path = os.path.join(config.INPUT_DIR, 'sites', meraki_network_names[0], filename)

            with open(file_path, 'r') as f:
                csv_reader = csv.DictReader(f)
                try:
                    row = next(csv_reader)  # Get only the first row of data
                except StopIteration:
                    raise ValueError("CSV file is empty or has no data rows after header.")

                # Build dictionary using headers as keys and the single row as values
                site_dict = {meraki_network_names[0]: {key: value for key, value in row.items()}}

        site_data = build_combined_data(site_dict, standard_vlans)
        for meraki_network_name in meraki_network_names:
            meraki_network_id = get_meraki_network_id(meraki_network_name, meraki_networks)
            meraki_vlans(site_data, meraki_network_name, meraki_network_id, args.a, args.u)

    if args.vlans_report:
        vlan_missing_report(meraki_networks, standard_vlans)

    if args.ports:
        if args.multi_site:
            filename = args.ports
            site_path = os.path.join(config.INPUT_DIR, filename)

            data_list = []  # This will store the rows as dictionaries
            with open(site_path, 'r') as f:
                csv_reader = csv.DictReader(f)
                # Iterate through the rows and append them to the list
                for row in csv_reader:
                    # `row` is already a dictionary with keys as the CSV headers
                    data_list.append(row)
        else:
            filename = args.ports
            file_path = os.path.join(config.INPUT_DIR, 'sites', meraki_network_names[0], filename)
            data_list = []  # This will store the rows as dictionaries
            with open(file_path, 'r') as f:
                csv_reader = csv.DictReader(f)
                for row in csv_reader:
                    # `row` is already a dictionary with keys as the CSV headers
                    # Insert 'site_name' attribute into row before appending
                    row_with_site = {'site_name': meraki_network_names[0], **row}
                    data_list.append(row_with_site)

        for meraki_network_name in meraki_network_names:
            meraki_network_id = get_meraki_network_id(meraki_network_name, meraki_networks)
            update_meraki_ports(data_list, meraki_network_name, meraki_network_id, standard_vlans)
