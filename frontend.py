# Frontend to readout the lakeshore224 as a MIDAS equipment 
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
        names = list(data.keys())
        self.client.odb_set(f'{self.odb_settings_dir}/Names', names)

        

        # You can set the status of the equipment (appears in the midas status page)
        self.set_status("Initialized")

    def read_webpage(self):
        """Parse the webpage
        
        Returns:
            dict
        """

        # fetch
        req = requests.get(self.settings['hostname'])
        soup = BeautifulSoup(req.content, 'html.parser')
        table = soup.find('table', class_=self.TABLE_CLASS)

        if not table:
            raise RuntimeError(f'Cannot find data table "{self.TABLE_CLASS}"')

        # get data
        data = {}
        for row in table.find_all('tr'):
            name, value = [cell.text.strip() for cell in row.find_all('td')]
            name = name[:-1] # strip trailing colon

            if 'Time' in name:
                data[name] = parser.parse(value).timestamp()
            elif 'Pressure Tendency' == name:
                continue
            else:
                vals = value.split()
                value = float(vals[0])
                unit = "".join(vals[1:])
                data[f'{name}_{unit}'] = value

        return data        

    def readout_func(self):
        """Parse the webpage

        Returns:
            midas.event.Event|None: event with a single TID_DOUBLE bank holding
                the 12 channel temperatures in K, or None if the read failed.
        """

        # read data
        data = self.read_webpage()

        # bank names must be exactly 4 characters
        event = midas.event.Event()
        event.create_bank(self.BANK_NAME, midas.TID_DOUBLE, 
                          np.fromiter(data.values(), dtype=np.float64))

        return event

class WeatherFrontend(midas.frontend.FrontendBase):
    def __init__(self):
        midas.frontend.FrontendBase.__init__(self, "WeatherFE")
        self.add_equipment(WeatherEquipment(self.client))

if __name__ == "__main__":
    with WeatherFrontend() as fe:
        fe.run()
