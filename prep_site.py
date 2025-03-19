import json
import argparse
import logging
import os
from utils import setup_logging, get_meraki_network_id
import config
import sys
import shutil
import filecmp
from dotenv import load_dotenv

env_path = os.path.join(os.path.expanduser("~"), ".env")
load_dotenv()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Meraki Site Preparation Tool")

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        '--site_name',
        type=str,
        required=True,
        help='Site name'
    )

    args = parser.parse_args()

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

    # Validate the site_name provided exists in Meraki Dashboard. If it exists, it will return a network id.
    meraki_networks = fetch_meraki_networks(dashboard, MERAKI_ORG_ID)
    if get_meraki_network_id(args.site_name, meraki_networks) is None:
        logger.critical(f'Site {args.site_name} does not exist in Meraki.')
        raise SystemExit(1)

    sites_file = os.path.join(config.INPUT_DIR, 'sites.txt')
    # Write the provided site_name to sites_file (overwriting existing content is allowed)
    try:
        with open(sites_file, 'w') as f:
            f.write(args.site_name + '\n')
        logger.info(f"Successfully wrote site name '{args.site_name}' to {sites_file}")
    except IOError as e:
        logger.error(f"Failed to write site name into {sites_file}: {e}")
        raise SystemExit(1)

    global_vlans = os.path.join(config.INPUT_DIR, 'vlans.json')
    sample_vlans = os.path.join(config.INPUT_DIR, 'samples', 'vlans.json')

    if not os.path.exists(global_vlans):
        logger.error(f'⚠️ Missing configuration file: {global_vlans}')
        print(f'''
    ============================================================
    🚫 ERROR: VLAN Configuration File Missing!

    Please perform the following steps:
    1️⃣ Copy the sample VLAN configuration file:
        From: {sample_vlans}
        To:   {global_vlans}

    2️⃣ Modify the copied vlans.json file to match your organization's specific configuration.

    3️⃣ Run this script again after making necessary modifications.
    ============================================================
    ''')
        sys.exit(1)

    # Check if global_vlans is exactly identical to the sample_vlans, warn user clearly if so.
    if os.path.exists(sample_vlans) and filecmp.cmp(global_vlans, sample_vlans, shallow=False):
        logger.error(f'⚠️ Detected unmodified configuration file: {global_vlans}')
        print(f'''
    ============================================================
    ⚠️ WARNING: Unmodified VLAN Configuration Detected!

    Your VLAN configuration file {global_vlans} appears identical to the sample provided.

    Please edit your vlans.json file to specifically define VLAN details relevant to your organization before proceeding.

    After modifications:
    ✅ Save the file {global_vlans}.
    ✅ Run this script again.

    Exiting now.
    ============================================================
    ''')
        sys.exit(1)

    # make sure the sites directory exists
    site_directory = os.path.join(config.INPUT_DIR, 'sites', args.site_name)
    os.makedirs(site_directory, exist_ok=True)
    samples_dir = 'samples'
    # Load the vlans.json file
    with open(global_vlans, 'r') as file:
        vlan_data = json.load(file)

    # Go through each VLAN definition and create directories if DHCP Server is True
    for vlan_name, vlan_details in vlan_data.items():
        if vlan_details.get('DHCP Server') is True:
            vlan_dir = os.path.join(site_directory, vlan_name)
            os.makedirs(vlan_dir, exist_ok=True)
            logger.info(f"Created directory: {vlan_dir}")
            for csv_filename in ['fixed.csv', 'reserved.csv', 'dhcp.json']:
                src_csv = os.path.join(samples_dir, csv_filename)
                dst_csv = os.path.join(vlan_dir, csv_filename)
                if os.path.exists(src_csv):
                    shutil.copyfile(src_csv, dst_csv)
                    logger.info(f"Copied {csv_filename} to {vlan_dir}")
                else:
                    logger.warning(f"Missing sample file: {src_csv}, skipped copying.")

        else:
            logger.debug(f"Skipped VLAN: {vlan_name}, DHCP Server not enabled.")

    # copy the site specific files to the site directory
    for site_filenames in ['subnets.csv', 'mx_ports.csv']:
        src_file = os.path.join(samples_dir, site_filenames)
        dst_file = os.path.join(site_directory, site_filenames)
        if os.path.exists(src_file):
            shutil.copyfile(src_file, dst_file)
            logger.info(f"Copied {site_filenames} to {site_directory}")
        else:
            logger.warning(f"Missing sample file: {src_file}, skipped copying.")

    # Now ceeate the headers in the subnets.csv file, they are the keys from vlans.json
    headers = []
    for vlan_name, vlan_details in vlan_data.items():
        headers.append(vlan_name)
    subnets_csv = os.path.join(site_directory, 'subnets.csv')
    with open(subnets_csv, 'w') as file:
        file.write(','.join(headers) + '\n')
        logger.info(f"Created {subnets_csv}")

    # Site-level instructions
    print("\n" + "=" * 60)
    print(f"🎉 Setup completed for site '{args.site_name}'!")
    print("=" * 60 + "\n")

    print("📁 **Site-level configuration files to edit:**")
    print(f"  - {os.path.join(site_directory, 'mx_ports.csv')}")
    print(f"  - {os.path.join(site_directory, 'subnets.csv')}\n")

    # Instructions for VLAN directories
    dhcp_vlans = [vlan_name for vlan_name, details in vlan_data.items() if details.get('DHCP Server') is True]

    if dhcp_vlans:
        print("🛠 **VLAN-specific configuration files to edit:**")
        for vlan_name in dhcp_vlans:
            vlan_dir = os.path.join(site_directory, vlan_name)
            print(f"\n  ➡️ VLAN '{vlan_name}':")
            print(f"      - {os.path.join(vlan_dir, 'dhcp.json')}")
            print(f"      - {os.path.join(vlan_dir, 'fixed.csv')}")
            print(f"      - {os.path.join(vlan_dir, 'reserved.csv')}")
    else:
        print("ℹ️  No VLANs with DHCP server enabled were found.")

    print("\n✅ **All directories and initial files are created successfully!**")
    print("=" * 60 + "\n")