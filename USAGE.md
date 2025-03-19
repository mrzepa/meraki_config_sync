# Multisite Updates
This script can be used to make changes to multiple sites at once with the `-m` option.

## Creating the Ports CSV File

The ports CSV file specifies the configuration details for ports that will be updated or managed in the Meraki networks. This file should be placed in the `input` directory and follows a specific structure as described below.

### Example Ports CSV File
Here is an example of the ports CSV file (`mx_ports.csv`):
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
- **secure**: Specifies whether port security is enabled (`y`) or disabled (`n`). Note, this will set port security to `hybrid` mode.

### Steps to Create the Ports CSV File
1. Navigate to the `input` directory in your project folder.
2. Create a new file called `mx_ports.csv`.
3. Add the configuration details for each port, using the columns shown above. Ensure the data is valid:

### Notes
- Each row in the CSV file represents one port's configuration.
- The `number` column must specify the port number as a string or integer.
- If the `secure` column is set to `y`, the port will use a hybrid-radius (802.1x fallback to MAB) access policy. If set to `n`, it will use an open access policy. It is ignored for trunk port.
---
## Creating the VLANs CSV File

The VLANs CSV file specifies VLAN details, including site-specific network prefixes, that will be added or updated in Meraki networks. This file should be placed in the `input` directory and follows a predefined structure.

### Example Subnets CSV File
Here is an example of a VLANs CSV file (`subnets.csv`):
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

### Steps to Create the Subnets CSV File
1. Navigate to the `input` directory in your project folder.
2. Create a file called `subnets.csv`.
3. For each site, add a row specifying:
   - The **site_name** (must match a Meraki network).
   - The subnet prefixes for applicable VLAN categories (leave blank for unconfigured VLANs, or vlans that you do not want to add/update at this site).

### Notes
- Only include VLAN categories that are relevant for your network configurations.
- Ensure the correct subnet assignments for each site to prevent IP conflicts.
