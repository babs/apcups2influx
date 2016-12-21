#!/usr/bin/python

import socket, struct, codecs, logging, os, sys
import datetime, time, calendar
from pprint import pprint

try:
    # For Python 3.0 and later
    from urllib.request import urlopen, Request
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen, Request

logging.basicConfig(format="%(asctime)s %(name)-15s %(levelname)-8s %(message)s")
log = logging.getLogger("apcups2influx")


class ApcUpsNIS(object):
    UNITS = ( # from apcaccess.c [removed \n]
        " Minutes",
        " Seconds",
        " Percent",
        " Volts",
        " Watts",
        " Hz",
        " C",
    )
    
    field_mapping = {
        'TONBATT':  "seconds_on_battery",
        'LOADPCT':  "ups_load_percent",
        'TIMELEFT': "time_left_minute",
        'ITEMP':    "internal_temperature",
        'NOMOUTV':  "output_nominal_voltage",
        'BATTV':    "battery_current_voltage",
        'BCHARGE':  "battery_charge_percent",
        'NOMBATTV': "battery_nominal_voltage",
        'LINEFREQ': "line_current_freq",
        'LINEV':    "line_input_voltage",
        'MAXLINEV': "line_maximum_voltage",
        'MINLINEV': "line_minimum_voltage",
        'OUTPUTV':  "output_current_voltage",
        'STATUS': "ups_status",
    }

    str_field = ['STATUS']
        
    def __init__(self, host, port=3551):
        self.port = port
        self.host = host
        self._connect()
        
    def _connect(self):
        log.debug("Connect")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

    def status(self, strip_units=False):
        ret = {}
        retlines = self._netwrite("status")
        for line in retlines:
            (key, val) = map(lambda x: x.strip(), line.split(':', 1))
            if strip_units:
                for unit in ApcUpsNIS.UNITS:
                    if val.endswith(unit):
                        val = val[:-len(unit)]
            ret[key] = val
        return ret

    def _netwrite(self, msg):
        self.sock.send(struct.pack('!h',len(msg))+msg)
        lines = []
        while True:
            net_pksize = self.sock.recv(2)
            if len(net_pksize) != 2:
                self._connect()
                break
                
            (pksize,) = struct.unpack("!h", net_pksize)
            if pksize == 0:
                break
            lines.append(self.sock.recv(pksize))
        return lines

    @staticmethod
    def parse_date(date):
        date, tz_info = date[:-5], date[-5:]
        neg, hours, minutes = tz_info[0], int(tz_info[1:3]), int(tz_info[3:])
        if neg == '+':
            hours, minutes = hours * -1, minutes * -1
        return calendar.timegm(
            (datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S ") + datetime.timedelta(hours=hours, minutes=minutes)).timetuple())

def main():
    log.setLevel(int(os.environ.get("DEBUGLEVEL", "20")))
    influxurls = []
    influx_instances = os.environ.get("INFLUXDB", "localhost:8086:apcups")
    
    try:
        for influxdef in influx_instances.split(" "):
            influxparams = influxdef.split(":")
            try:
                req = Request("http://%s:%s/query" % (influxparams[0], influxparams[1]),
                                      codecs.encode("q=CREATE+DATABASE+\"%s\"" % influxparams[2], 'utf-8'))
                urlopen(req)
                influxurls.append("http://{0}:{1}/write?db={2}".format(*influxparams))
            except Exception as exc:
                log.error("Unable to connect to following instance, dropping it: %s:%s",
                          influxparams[0], influxparams[1],
                          exc_info=exc)
    except Exception as exc:
        log.error('Failed to parse env:INFLUXDB', exc_info=exc)

    if len(influxurls) == 0:
        log.error("No influxdb instance to send to.")
        sys.exit(1)
    #
    apcnis = ApcUpsNIS(sys.argv[1])
    i = 1
    while True:
        apcdata = apcnis.status(True)
        sample = {}
        for k,v in ApcUpsNIS.field_mapping.items():
            if k in apcdata:
                if k in ApcUpsNIS.str_field:
                    sample[v] = '"'+apcdata[k].replace('"','\\"')+'"'
                else:
                    sample[v] = apcdata[k]
        measurement = "smartups,serial=%s,model=%s"%(apcdata['SERIALNO'],apcdata['MODEL'].replace(' ', '\\ '))
        influxts = ApcUpsNIS.parse_date(apcdata['DATE'])*10**9
        for influxurl in influxurls:
            post = codecs.encode(
                "%s %s %s"%(measurement, ','.join([x+"="+y for x,y in sample.items()]) , influxts),
                'utf-8')
            req = Request(influxurl, post)
            urlopen(req)
            sys.stdout.write('.')
            if i%10 == 0:
                sys.stdout.write(' ')
            if i%100 == 0:
                sys.stdout.write(str(i))
                sys.stdout.write("\n")
                i = 0
            i += 1
            sys.stdout.flush()
        #pprint(apcdata)
        #pprint(sample)
        time.sleep(5)
        
if __name__ == "__main__":
    main()
