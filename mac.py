import re
class MacAddress:
    """
    Class to define a MAC address.
    Methods in this class can convert the MAC address string into several popular formats.
    """

    def __init__(self, mac_address):
        self.NoDelim = None
        self.mac_address = mac_address

    @property
    def mac_address(self):
        return self._mac_address

    @mac_address.setter
    def mac_address(self, val):
        if not self.is_valid_macaddr802(val):
            raise ValueError(f'The MAC address {val} is not valid.')
        if ':' in val:
            self.NoDelim = val.replace(':', '')
        elif '.' in val:
            self.NoDelim = val.replace('.', '')
        elif '-' in val:
            self.NoDelim = val.replace('-', '')
        else:
            self.NoDelim = val
        self._mac_address = val

    @mac_address.deleter
    def mac_address(self):
        del self._mac_address

    @staticmethod
    def insert(my_str: str, group: int, char: str) -> str:
        """
        Split a string and insert a character
        :param my_str: String to instert character into
        :param group: number of chacaters between the new char
        :param char: character to insert
        :return: new string with the inserted character
        """
        my_str = str(my_str)
        return char.join(my_str[i:i+group] for i in range(0, len(my_str), group))

    def convert_mac_address(self, character: str) -> str:
        """
        Convert the mac address for the specified delimeter
        :param character: one of : . - or "aruba" which will put a dash in the middle of the string.
        :return:
        """
        match character:
            case ':':
                return self.insert(self.NoDelim, 2, ':')
            case '.':
                return self.insert(self.NoDelim, 4, '.')
            case '-':
                return self.insert(self.NoDelim, 2, '-')
            case 'aruba' | 'Aruba':
                return self.insert(self.NoDelim, 6, '-')

    @staticmethod
    def is_valid_macaddr802(value: str) -> bool:
        """
        Determine if the input value is a valid mac address
        :param value: str: string to test.
        :return: bool
        """
        allowed = re.compile(r"""
                             (
                                 ^([0-9A-F]{2}[-]){5}([0-9A-F]{2})$
                                |^([0-9A-F]{2}[:]){5}([0-9A-F]{2})$
                                |^([0-9A-F]{6}[-]){1}([0-9A-F]{6})$
                                |^([0-9A-F]{4}[.]){2}([0-9A-F]{4})$
                                |^([0-9A-F]{12})$
                             )
                             """,
                             re.VERBOSE | re.IGNORECASE)

        if allowed.match(value) is None:
            return False
        else:
            return True
