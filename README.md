# Meraki Site Update Tool

This project provides a series of tools for managing and synchronizing VLAN and port configurations for networks in the Meraki Dashboard. It allows you to add missing VLANs, update existing VLANs, generate reports, and update switch port configurations in bulk.

---

## Features

1. Add missing VLANs to Meraki networks.
2. Update existing VLAN configurations with new details.
3. Generate reports on missing or mismatched VLANs across networks.
4. Bulk update switch port configurations in Meraki MX Firewalls.
5. Includes backup functionality to save current configurations before applying changes.

---
## Requirements
- Python 3.12+
- API Key For Meraki Dashboard
- Meraki Org ID

---
## Setup Instructions

Follow the steps below to configure and run the tool:

### 1. Clone the Project
Clone the project repository to your local machine:
```bash
git clone https://github.com/mrzepa/meraki_config_sync.git
cd meraki_config_sync
```

### 2. Install Required Dependencies
Install the required Python dependencies using `pip`:
```bash
python3 -m venv venv    # Create a virtual environment
source venv/bin/activate    # Activate it (use `venv\Scripts\activate` for Windows)
pip install -r requirements.txt    # Install dependencies
```

### 3. Configure `config.py`
The `config.py.SAMPLE` file contains default configuration settings. To use this file:
1. Copy `config.py.SAMPLE` to `config.py`:
   ```bash
   cp sample/config.py.SAMPLE config.py
   ```
2. Make necessary adjustments to the directory paths in `config.py`, if needed. By default, the following directories will be created:
   - **input** (for input files)
   - **output** (for output files)
   - **cache** (for caching network data)
   - **backup** (for storing configuration backups)

### 4. Set Up `.env` File
You need to create a `.env` file in your home directory to provide your **Meraki API key** and **organization ID**:
```bash
touch .env
```

Add the following lines to the `.env` file:
```env
MERAKI_API_KEY=your_meraki_api_key_here
MERAKI_ORG_ID=your_meraki_organization_id_here
```

Replace `your_meraki_api_key_here` and `your_meraki_organization_id_here` with your actual Meraki API credentials.

---
### 5. Creating the `vlans.json` File

The `vlans.json` file defines the standard VLAN configurations for your Meraki networks. This file should be placed in the `input` directory and follows the JSON format as described below.

A sample vlans.json file can be found in the `samples` directory.
#### Example `vlans.json`
Here is an example of the `vlans.json` structure:
```json
{
  "Guest": {
    "ID": 2,
    "VPN Mode": false,
    "DHCP Server": true
  },
  "Management": {
    "ID": 3,
    "VPN Mode": true,
    "DHCP Server": false
  },
  "VOICE": {
    "ID": 4,
    "VPN Mode": true,
    "DHCP Server": true
  }
}
```
### Explanation of the Fields
- **Key (VLAN Name):** A string representing the VLAN name (e.g., `"Guest"`, `"Management"`).
- **ID:** A unique integer representing the VLAN ID (e.g., 2, 3).
- **VPN Mode:** Bool value to specify whether the VPN mode for the VLAN is `"true"` or `"false"`.
- **DHCP Server:** Bool value indicating if a DHCP server should be enabled on this VLAN.

### Steps to Create `vlans.json`
1. Navigate to the `input` directory in your project folder.
2. Create a new file called `vlans.json` or copy the one from `samples` directory.
3. Populate the file with your standard VLAN configurations. Follow the structure shown in the example.

### Notes
- Ensure the file uses valid JSON syntax.
- Each VLAN name should be unique, and the VLAN IDs should not conflict within a network.
- Only specify the VLANs you'll be managing in the Meraki networks.

By providing the `vlans.json` file, the tool can efficiently compare and synchronize VLANs across networks.
## Individual Site Settings

To update settings that are local to one site only, create a directory under `input` called `sites`. Under `sites`, create another directory using the Meraki `network_name` for the specific site. 

The script `prep_site.py` can be executed to automatically generate the site specific files and directory structure. It requires that the `vlans.json` file already be properly populated in the `input` directory.

```bash
python prep_site.py --site-name "my meraki site"
```

The structure should look like the following:
```Text
input/
└── sites/
    └── <meraki_network_name>/
        ├── mx_ports.csv             # Port settings for MX devices
        ├── subnets.csv              # Local VLAN configurations
        └── <VLAN name>/             # VLAN-specific DHCP configurations
            ├── dhcp.json            # DHCP server settings in JSON format (DNS, DHCP options, etc.)
            ├── reserved.csv         # Reserved IP address entries (same format as Meraki Dashboard files)
            └── fixed.csv            # Fixed IP address entries (same format as Meraki Dashboard files)
```
### File Details:

| File / Directory          | Description                                                                                                              |
|---------------------------|--------------------------------------------------------------------------------------------------------------------------|
| `mx_ports.csv`            | Contains port-specific settings for MX appliances. Follow the PORTS CSV example above, but omit the `site_name`.         |
| `subnets.csv`             | Contains information for adding local VLANs. Follow the VLANs CSV example above, but omit the `site_name`.           |
| `<VLAN_name>/dhcp.json`   | Contains DHCP server settings (like DNS servers, DHCP options, etc.) for a VLAN in JSON format.                          |
| `<VLAN_name>/reserved.csv`| Contains reserved DHCP IP address entries. Use the same format as you do when uploading entries via the Meraki Dashboard. |
| `<VLAN_name>/fixed.csv`   | Contains fixed DHCP IP address entries. Use the same format as you do when uploading fixed IPs via the Meraki Dashboard. |

Ensure that you strictly follow this naming and structure convention. This approach enables clear organization, easy maintenance, and smooth automation of site-specific configurations.

You will need to edit each of these files with the local settings of the site.

## How to Use

You can run the tool via command-line options. Examples of common use cases are:

### Add Missing VLANs
To add missing VLANs to the specified site from the `subnets.csv` file:
```bash
python meraki_site_update.py  --vlans -a
```

### Update Existing VLANs
To update existing VLANs based on the `vlans.json` file:
```bash
python meraki_site_update.py  --vlans -u
```

### Update Switch Ports
To update switch port configurations based on the `mx_ports.csv` file:
```bash
python meraki_site_update.py --ports
```

### Add and Update VLANs for Multiple Sites
You can use a file containing a list of site names to apply changes to multiple networks:
```bash
python meraki_site_update.py --site-names-file sites.txt --vlans -aum
````

### Add and Update VLANs, and ports at the same time.
```bash
python meraki_site_update.py  --vlans -au --ports
```
### Generate VLAN Report
To generate a report showing missing or mismatched VLANs for all networks:
```bash
python meraki_site_update.py --vlans-report
```

---

## Logs and Output

- **Logs:** Detailed logs will be available in the console. Enable verbose logging with `--verbose`.
- **Output Files:** Reports and changes will be saved in the `output` directory.
- **Backups:** Existing configurations will be saved in the `backup` directory before applying updates.

---

## Notes

1. Ensure that your Meraki API key has the appropriate permissions for the operations (read/write).
2. Do not hard-code sensitive information (such as API keys) in scripts; always use the `.env` file.

---

## Contributing
Feel free to fork this repository and submit pull requests for any enhancements or bug fixes.

For issues or questions, open a ticket in the issue tracker.

---

## License
This project is licensed under [MIT License](LICENSE).

