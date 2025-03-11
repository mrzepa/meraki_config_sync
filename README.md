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
   cp config.py.SAMPLE config.py
   ```
2. Make necessary adjustments to the directory paths in `config.py`, if needed. By default, the following directories will be created:
   - **input** (for input files)
   - **output** (for output files)
   - **cache** (for caching network data)
   - **backup** (for storing configuration backups)

### 4. Set Up `.env` File
You need to create a `.env` file in the project directory to provide your **Meraki API key** and **organization ID**:
```bash
touch .env
```

Add the following lines to the `.env` file:
```env
MERAKI_API_KEY=your_meraki_api_key_here
MERAKI_ORG_ID=your_meraki_organization_id_here
```

Replace `your_meraki_api_key_here` and `your_meraki_organization_id_here` with your actual Meraki API credentials.

### 5. Prepare Input Files

- **VLANs File**: A `CSV` file containing VLAN details to add or update. Place this file in the `input` directory.
- **Sites File (optional)**: A text file with a list of site names (one per line). Place this file in the `input` directory.
- **Ports File**: A `CSV` file containing switch port configuration details. Place this file in the `input` directory.

## Creating the Ports CSV File

The ports CSV file specifies the configuration details for ports that will be updated or managed in the Meraki networks. This file should be placed in the `input` directory and follows a specific structure as described below.

### Example Ports CSV File
Here is an example of the ports CSV file (`ports.csv`):
```csv
site_name,number,type,vlan,secure
site 1,7,access,2,y
site 1,9,access,3,n
site 2,10,access,4,n
site 2,11,trunk,5,y

```

### Explanation of the Columns
- **site_name**: The name of the site where the port configuration will be applied. This must match exactly with the Meraki network name.
- **number**: The port number to be updated (e.g., `7`, `9`).
- **type**: The port type, either `access` or `trunk`.
  - `access`: Connects a port to a single VLAN.
  - `trunk`: Allows the port to carry traffic for multiple VLANs.
- **vlan**: The assigned VLAN ID for an `access` port or native VLAN ID for a `trunk` port (must match a valid VLAN from the `vlans.json` file).
- **secure**: Specifies whether port security is enabled (`y`) or disabled (`n`).

### Steps to Create the Ports CSV File
1. Navigate to the `input` directory in your project folder.
2. Create a new file called `ports.csv`.
3. Add the configuration details for each port, using the columns shown above. Ensure the data is valid:

### Notes
- Each row in the CSV file represents one port's configuration.
- The `number` column must specify the port number as a string or integer.
- If the `secure` column is set to `y`, the port will use a hybrid-radius (802.1x fallback to MAB) access policy. If set to `n`, it will use an open access policy. It is ignored for trunk port.
---
## Creating the VLANs CSV File

The VLANs CSV file specifies VLAN details, including site-specific network prefixes, that will be added or updated in Meraki networks. This file should be placed in the `input` directory and follows a predefined structure.

### Example VLANs CSV File
Here is an example of a VLANs CSV file (`vlans.csv`):
```csv
site_name,Guest,Management,VOICE
site 1,192.168.5.1/24,,192.168.10.2/24
```

### Explanation of the Columns
- **site_name**: The name of the site where the VLAN configuration will be applied. This must match exactly with the Meraki network name.
- **List of Vlans**:
   - These are predefined VLAN categories from the `vlans.json` file. Each column represents the **subnet prefix** for that VLAN at the site.
   - Example: `192.168.5.1/24` is a subnet prefix for the "Guest" VLAN.
   - Add as many vlans to the header as you need. This can not exceed the number of vlans defined in the `vlans.json` file.

### Rules for Preparing the VLANs CSV File
1. A VLAN category (column) should be left blank if it’s not applicable for the site.
2. Ensure that the VLAN category names exactly match the keys in your `vlans.json` file to avoid mismatches.
3. Each subnet prefix must follow the format `<network_address>/<prefix_length>` (e.g., `192.168.5.1/24`).

### Steps to Create the VLANs CSV File
1. Navigate to the `input` directory in your project folder.
2. Create a file called `vlans.csv`.
3. For each site, add a row specifying:
   - The **site_name** (must match a Meraki network).
   - The subnet prefixes for applicable VLAN categories (leave blank for unconfigured VLANs, or vlans that you do not want to add/update at this site).

### Notes
- Only include VLAN categories that are relevant for your network configurations.
- Ensure the correct subnet assignments for each site to prevent IP conflicts.

---
### 6. Creating the `vlans.json` File

The `vlans.json` file defines the standard VLAN configurations for your Meraki networks. This file should be placed in the `input` directory and follows the JSON format as described below.

#### Example `vlans.json`
Here is an example of the `vlans.json` structure:
```json
{
  "Guest": {
    "ID": 2,
    "VPN Mode": "Disabled"
  },
  "Management": {
    "ID": 3,
    "VPN Mode": "Enabled"
  },
  "VOICE": {
    "ID": 4,
    "VPN Mode": "Enabled"
  }
}
```

### Explanation of the Fields
- **Key (VLAN Name):** A string representing the VLAN name (e.g., `"Guest"`, `"Management"`).
- **ID:** A unique integer representing the VLAN ID (e.g., 2, 3).
- **VPN Mode:** A string field to specify whether the VPN mode for the VLAN is `"Enabled"` or `"Disabled"`.

### Steps to Create `vlans.json`
1. Navigate to the `input` directory in your project folder.
2. Create a new file called `vlans.json`.
3. Populate the file with your standard VLAN configurations. Follow the structure shown in the example.

### Notes
- Ensure the file uses valid JSON syntax.
- Each VLAN name should be unique, and the VLAN IDs should not conflict within a network.
- Only specify the VLANs you'll be managing in the Meraki networks.

By providing the `vlans.json` file, the tool can efficiently compare and synchronize VLANs across networks.

## How to Use

You can run the tool via command-line options. Examples of common use cases are:

### Add Missing VLANs
To add missing VLANs to the specified site:
```bash
python meraki_site_update.py --site-name "My Site Name" --vlans vlans.csv -a
```

### Update Existing VLANs
To update existing VLANs based on the provided VLAN file:
```bash
python meraki_site_update.py --site-name "My Site Name" --vlans vlans.csv -u
```

### Generate VLAN Report
To generate a report showing missing or mismatched VLANs for all networks:
```bash
python meraki_site_update.py --vlans-report
```

### Update Switch Ports
To update switch port configurations based on a port file:
```bash
python meraki_site_update.py --site-name "My Site Name" --ports ports.csv
```

### Add or Update VLANs for Multiple Sites
You can use a file containing a list of site names to apply changes to multiple networks:
```bash
python meraki_site_update.py --site-names-file sites.txt --vlans vlans.csv -a
```

---

## Example Workflow

### 1. Add Missing VLANs
1. Prepare a VLAN CSV file per the instruction above.
   
2. Run the command:
   ```bash
   python meraki_site_update.py --site-name "My Site Name" --vlans vlans.csv -a
   ```
### 2. Update Existing VLANs
1. Prepare a VLAN CSV file per the instruction above.
   
2. Run the command:
   ```bash
   python meraki_site_update.py --site-name "My Site Name" --vlans vlans.csv -u
   ```
NOTE: You can use the -a and -u flags at the same time. This will add any missing vlans and update existing ones.

### 3. Update Meraki MX ports
1. Prepare a PORTS CSV file per the instruction above.
   
2. Run the command:
   ```bash
   python meraki_site_update.py --site-name "My Site Name" --ports ports.csv
   ```
### 4. Generate VLAN Report
Run the command to check for VLAN mismatches or missing VLANs:
```bash
python meraki_site_update.py --vlans-report
```

This will generate a `vlan_report.json` file in the `output` directory.

### Notes

- You can use the `--ports` and `--vlans` options at the same time. This allows you to update both the VLANs and ports in a single command, streamlining the workflow.
- For example:
  ```bash
  python meraki_site_update.py --site-name "My Site Name" --ports ports.csv --vlans vlans.csv
  ```
  This will update the VLANs based on the `vlans.csv` file and configure the ports using the `ports.csv` file.

- Make sure both the VLAN and port configuration files are prepared according to the instructions mentioned above for best results.
---

## Logs and Output

- **Logs:** Detailed logs will be available in the console. Enable verbose logging with `--verbose`.
- **Output Files:** Reports and changes will be saved in the `output` directory.
- **Backups:** Existing configurations will be saved in the `backup` directory before applying updates.

---

## Notes

1. **Testing Mode:** Use the `--test` flag for a dry run without applying any changes.
2. Ensure that your Meraki API key has the appropriate permissions for the operations (read/write).
3. Do not hard-code sensitive information (such as API keys) in scripts; always use the `.env` file.

---

## Contributing
Feel free to fork this repository and submit pull requests for any enhancements or bug fixes.

For issues or questions, open a ticket in the issue tracker.

---

## License
This project is licensed under [MIT License](LICENSE).

