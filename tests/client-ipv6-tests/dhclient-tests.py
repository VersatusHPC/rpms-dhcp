#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1+
# ~~~
#   Description: DHCPv6 Tests for dhclient - a DHCP client
#
#   Author: Susant Sahani <susant@redhat.com>
#   Copyright (c) 2018 Red Hat, Inc.
# ~~~

import errno
import os
import sys
import time
import unittest
import subprocess
import signal
import shutil
import socket
from pyroute2 import IPRoute

DHCLIENT_CI_DIR='/var/run/dhclient-ci'

DHCP6S_CONFIG_FILE_POOL='/var/run/dhclient-ci/dhcp6s-pool.conf'
DHCP6S_CONFIG_FILE_DUID='/var/run/dhclient-ci/dhcp6s-duid.conf'
DHCP6S_CONFIG_FILE_DNS='/var/run/dhclient-ci/dhcp6s-dns.conf'

DHCP6S_PID_FILE='/var/run/dhclient-ci/dhcp6s-test.pid'

DHCLIENT_CONFIG_FILE='/var/run/dhclient-ci/dhclient-ci.conf'
DHCLIENT_CONFIG_FILE_DUID='/var/run/dhclient-ci/dhclient-ci-duid.conf'

DHCLIENT_PID_FILE='/var/run/dhclient-ci/dhclient-test.pid'
DHCLIENT_LEASE_FILE='/var/run/dhclient-ci/dhclient.leases'
DHCLIENT_LOG_FILE='/var/run/dhclient-ci/dhclient-test-log'
DHCLIENT_TCP_DUMP_FILE='/tmp/dhclient-tcp-dump.pcap'

RADVD_CONFIG_FILE='/var/run/dhclient-ci/radvd.conf'
RADVD_PID_FILE='/var/run/dhclient-ci/radvd.pid'
RADVD_LOG_FILE='/var/run/dhclient-ci/radvd.log'

RESOLVE_CONF='/etc/resolv.conf'

def setUpModule():
    """Initialize the environment, and perform sanity checks on it."""

    if shutil.which('dhclient') is None:
        raise OSError(errno.ENOENT, 'dhclient not found')
    if shutil.which('dhcp6s') is None:
        raise OSError(errno.ENOENT, 'dhcp6s not found')
    if shutil.which('radvd') is None:
        raise OSError(errno.ENOENT, 'radvd not found')

def tearDownModule():
    pass

class GenericUtilities():
    """Provide a set of utility functions start stop daemons. write config files etc """

    def StartDhcp6s(self, config_file):
        """Start dhcp6s"""
        subprocess.check_output(['dhcp6s', '-c', config_file, 'veth-peer', '-dD', '-P', DHCP6S_PID_FILE])

    def StartRadvd(self):
        """Start radvd"""

        subprocess.check_output(['radvd', '-d5', '-C', RADVD_CONFIG_FILE, '-p', RADVD_PID_FILE, '-l', RADVD_LOG_FILE])

    def StartDhClient(self, config_file):
        """Start dhclient """
        subprocess.check_output(['dhclient', '-6', '-v', '-nw', '-pf', DHCLIENT_PID_FILE, '-cf', config_file, '-lf', DHCLIENT_LEASE_FILE, 'veth-test']).rstrip().decode('utf-8')
        self.addCleanup(os.remove, DHCLIENT_LEASE_FILE)

    def StopDaemon(self, pid_file):

        with open(pid_file, 'r') as f:
            pid = f.read().rstrip(' \t\r\n\0')
            os.kill(int(pid), signal.SIGTERM)

        os.remove(pid_file)

    def findTextInFile(self, log_file, **kwargs):
        """dnsmasq server logs."""

        if kwargs is not None:
            with open (log_file, 'rt') as in_file:
                contents = in_file.read()
                for key in kwargs:
                    self.assertRegex(contents, kwargs[key])

    def SetupVethInterface(self):
        """Setup veth interface"""

        ip = IPRoute()

        ip.link('add', ifname='veth-test', peer='veth-peer', kind='veth')
        idx_veth_test = ip.link_lookup(ifname='veth-test')[0]
        idx_veth_peer = ip.link_lookup(ifname='veth-peer')[0]

        ip.link('set', index=idx_veth_test, address='02:01:02:03:04:08')
        ip.link('set', index=idx_veth_peer, address='02:01:02:03:04:09')
        ip.link('set', index=idx_veth_test, state='up')
        ip.link('set', index=idx_veth_peer, state='up')
        ip.addr('add', index=idx_veth_peer, address='192.168.111.50')

        ip.close()

    def TearDownVethInterface(self):

        ip = IPRoute()

        ip.link('del', index=ip.link_lookup(ifname='veth-test')[0])
        ip.close()

class DhclientTests(unittest.TestCase, GenericUtilities):

    def setUp(self):
        self.SetupVethInterface()

    def tearDown(self):
        self.StopDaemon(DHCLIENT_PID_FILE)
        self.StopDaemon(DHCP6S_PID_FILE)
        self.StopDaemon(RADVD_PID_FILE)

        self.TearDownVethInterface()

    def test_dhclient_gets_rdnss_dnssl(self):
        """ dhclient gets the RDNSS DNSSL """

        self.StartDhcp6s(DHCP6S_CONFIG_FILE_DNS)
        self.StartRadvd()

        time.sleep(1)
        self.StartDhClient(DHCLIENT_CONFIG_FILE)
        time.sleep(10)
        output=subprocess.check_output(['ip','address', 'show', 'veth-test']).rstrip().decode('utf-8')

        # Address prefix
        self.assertRegex(output, "2001:888:db8:1::*")
        self.findTextInFile(RESOLVE_CONF,
                            dns1='2001:888:db8:1::a',
                            dns2='2001:888:db8:1::d',
                            search='test.com')

    def test_dhclient_gets_static_ip_address_using_duid(self):
        """ dhclient gets  addresse to hosts """

        self.StartDhcp6s(DHCP6S_CONFIG_FILE_DUID)
        self.StartRadvd()

        time.sleep(1)

        self.StartDhClient(DHCLIENT_CONFIG_FILE_DUID)
        time.sleep(10)
        output=subprocess.check_output(['ip','address', 'show', 'veth-test']).rstrip().decode('utf-8')

        # Address prefix
        self.assertRegex(output, "2001:888:db8:1::b")
        self.findTextInFile(RESOLVE_CONF,
                            dns='2001:888:db8:1::a',
                            search='test.com')

    def test_dhclient_assigns_address_from_pool(self):

        self.StartDhcp6s(DHCP6S_CONFIG_FILE_POOL)
        self.StartRadvd()

        time.sleep(1)

        self.StartDhClient(DHCLIENT_CONFIG_FILE)
        time.sleep(10)
        output=subprocess.check_output(['ip','address', 'show', 'veth-test']).rstrip().decode('utf-8')

        # Address prefix
        self.assertRegex(output, "2001:888:db8:1::*")
        self.findTextInFile(RESOLVE_CONF,
                            dns='2001:888:db8:1::a',
                            search='test.com')

if __name__ == '__main__':
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,
                                                     verbosity=3))
