# apcups2influx

`apcups2influx` is a small script that connects to [apcupsd](http://www.apcupsd.com/),
reads the status and sends it to the designated [InfluxDB](https://github.com/influxdata/influxdb) server(s).

## Usage

InfluxDB instances are taken from env variable:

`INFLUXDB`: InfluxDB instance(s) to push to (format: "instance1:port1:db1 instance2:port2:db2..."), default: localhost:8086:apcups

`apcupsd` ip is provided as first arg:

    apcups2influx.py <apcupsd-host>


## Todo

* use `argparse` instead of a mix of env / args
* startup scripts
  * SysV script
  * systemd script
* tests
