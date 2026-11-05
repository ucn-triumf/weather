# Frontend to readout the Meson hall weather station as a MIDAS equipment 
# Derek Fujimoto
# Sep 2026

import midas
import midas.frontend
import midas.event
import time
import requests
from bs4 import BeautifulSoup
from dateutil import parser
import numpy as np

class WeatherEquipment(midas.frontend.EquipmentBase):
    """Periodic equipment which parses the weather station on top of the meson hall.

    Attributes:
        read_failed (bool): whether the last readout raised, used to avoid
            rewriting the equipment status to the ODB on every cycle.
    """

    BANK_NAME = 'WTHR'
    TABLE_CLASS = 'sampdata' # html class of the table with the data. Pass to bs4

    def __init__(self, client):
        # The name of our equipment. This name will be used on the midas status
        # page, and our info will appear in /Equipment/MyPeriodicEquipment in
        # the ODB.
        equip_name = "OutsideWeather"

        default_common = midas.frontend.InitialEquipmentCommon()
        default_common.equip_type = midas.EQ_PERIODIC
        default_common.read_when = midas.RO_ALWAYS
        default_common.buffer_name = "SYSTEM"
        default_common.trigger_mask = 0
        default_common.event_id = 1
        default_common.period_ms = 1000
        default_common.log_history = 10

        default_settings = {'hostname': 'http://weather02.triumf.ca/latest.php'}

        midas.frontend.EquipmentBase.__init__(self, client, equip_name,
                                             default_common, default_settings)

        # test read and set settings
        data = self.read_webpage()
        self.client.odb_set(f'{self.odb_settings_dir}/Names {self.BANK_NAME}', 
                            [self.simplify_name(name) for name in data.keys()])

        full_names = [f'{name[:-1]} ({self.get_units(value)})' 
                        for name, value in data.items() if name != "Pressure Tendency:"]

        self.client.odb_set(f'{self.odb_settings_dir}/Full Names', full_names)
        
        # You can set the status of the equipment (appears in the midas status page)
        self.set_status("Initialized")
        self.read_failed = False

    @staticmethod
    def get_units(value):
        try:
            value = "".join(str(value).split()[1:])
        except ValueError: 
            value = ""
        else:
            value = value.replace('°C', 'C')
            value = value.replace('°', 'deg')
        return value

    @staticmethod
    def simplify_name(name):

        name = name.replace(':', '')
        name = name.replace('Absolute', 'Abs')
        name = name.replace('Average', 'Avg')
        name = name.replace('Direction', 'Dir')

        assert len(name) <= 31, f"Name '{name}' is too long! (length: {len(name)})"

        return name

    def read_webpage(self):
        """Parse the webpage
        
        Returns:
            dict
        """

        # fetch
        req = requests.get(self.settings['hostname'], timeout=10)

        if req.status_code != 200:
            raise RuntimeError(f'Webpage request failed with status {req.status_code}')

        soup = BeautifulSoup(req.content, 'html.parser')
        table = soup.find('table', class_=self.TABLE_CLASS)

        if not table:
            raise RuntimeError(f'Cannot find data table "{self.TABLE_CLASS}"')

        # extract data
        data = {}
        for row in table.find_all('tr'):
            name, value = [cell.text.strip() for cell in row.find_all('td')]

            # add data to dict
            if 'Time' in name:
                data[name] = parser.parse(value).timestamp()
            elif 'Pressure Tendency:' == name:
                continue
            else:
                value = value
                data[name] = value

        return data        

    def readout_func(self):
        """Parse the webpage

        Exceptions are caught so that transient failures (network, malformed
        page, bad values) don't kill the frontend. Failure and recovery are
        each logged once, on state change.

        Returns:
            midas.event.Event|None: event with a single TID_DOUBLE bank holding
                the weather station values, or None if the read failed.
        """

        try:
            # read data
            data = self.read_webpage()

            # simplify data keys and get values as floats
            data = {self.simplify_name(name):float(str(value).split()[0]) 
                        for name, value in data.items()}

            # make event
            event = midas.event.Event()
            event.create_bank(self.BANK_NAME, midas.TID_DOUBLE, 
                              np.fromiter(data.values(), dtype=np.float64))

        except Exception as err:
            if not self.read_failed:
                self.client.msg(f'Readout failed: {type(err).__name__}: {err}', is_error=True)
                self.set_status('Readout failed', status_color='redLight')
                self.read_failed = True
            return None

        # log recovery from a previous failure
        if self.read_failed:
            self.client.msg('Readout recovered')
            self.set_status('Running')
            self.read_failed = False

        return event

class WeatherFrontend(midas.frontend.FrontendBase):
    def __init__(self):
        midas.frontend.FrontendBase.__init__(self, "WeatherFE")
        self.add_equipment(WeatherEquipment(self.client))

if __name__ == "__main__":
    with WeatherFrontend() as fe:
        fe.run()
