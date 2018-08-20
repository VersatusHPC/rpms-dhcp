#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1+
# ~~~
#   Description: Tests for dhclient - a DHCP client
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

DHCLIENT_CONFIG_FILE='/var/run/dhclient-ci/test-dhclient.conf'
DHCLIENT_PID_FILE='/var/run/dhclient-ci/test-dhclient-test.pid'
DHCLIENT_LEASE_FILE='/var/run/dhclient-ci/test-dhclient.leases'
DHCLIENT_LOG_FILE='/var/run/dhclient-ci/test-dhclient-test-log'
DHCLIENT_TCP_DUMP_FILE='/var/run/dhclient-ci/test-dhclient-tcp-dump.pcap'

DNSMASQ_CONFIG_FILE='/var/run/dhclient-ci/test-dnsmasq.conf'
DNSMASQ_PID_FILE='/var/run/dhclient-ci/test-test-dnsmasq.pid'
DNSMASQ_LOG_FILE='/var/run/dhclient-ci/test-dnsmasq-log-file'

RESOLV_CONF='/etc/resolv.conf'

def setUpModule():
    """Initialize the environment, and perform sanity checks on it."""

    if shutil.which('dhclient') is None:
        raise OSError(errno.ENOENT, 'dhclient not found')

    if shutil.which('dnsmasq') is None:
        raise OSError(errno.ENOENT, 'dnsmasq not found')

def tearDownModule():
        pass

class GenericUtilities():
    """Provide a set of utility functions start stop daemons. write config files etc """

    def StartDnsMasq(self):
        """Start dnsmaq"""
        subprocess.check_output(['dnsmasq', '-8', DNSMASQ_LOG_FILE, '--log-dhcp', '--pid-file=/var/run/dhclient-ci/test-test-dnsmasq.pid',
                                 '--conf-file=/var/run/dhclient-ci/test-dnsmasq.conf', '-i', 'veth-peer', '-R'])

    def StartDhClient(self):
        """Start dhclient """
        subprocess.check_output(['dhclient', '-4', '-v', '-nw', '-pf', DHCLIENT_PID_FILE, '-cf', DHCLIENT_CONFIG_FILE, '-lf', DHCLIENT_LEASE_FILE, 'veth-test'])

    def StopDaemon(self, pid_file):
        with open(pid_file, 'r') as f:
            pid = f.read().rstrip(' \t\r\n\0')
            os.kill(int(pid), signal.SIGTERM)

        os.remove(pid_file)

    def SearchWordsInFile(self, log_file, **kwargs):
        """dnsmasq server logs."""

        if kwargs is not None:
            with open (log_file, 'rt') as in_file:
                contents = in_file.read()
                for key in kwargs:
                    self.assertRegex(contents, kwargs[key])

    def FindProtocolFieldsinTCPDump(self, **kwargs):
        """Look attributes in tshark."""

        contents = subprocess.check_output(['tshark', '-V', '-r', DHCLIENT_TCP_DUMP_FILE]).rstrip().decode('utf-8')
        if kwargs is not None:
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

    def StartCaptureBootpPackets(self):
        """Start thark to capture dhcp packets"""
        subprocess.check_output(['systemctl','start', 'tsharkd.service'])

    def StopCapturingPackets(self):
        subprocess.check_output(['systemctl', 'stop', 'tsharkd.service'])

class DhclientTests(unittest.TestCase, GenericUtilities):

    def setUp(self):
        """ setup veth and write radvd and dhcpv6configs """
        self.SetupVethInterface()

    def tearDown(self):
        self.StopDaemon(DHCLIENT_PID_FILE)
        self.StopDaemon(DNSMASQ_PID_FILE)

        os.remove(DHCLIENT_LEASE_FILE)

        self.TearDownVethInterface()

    def test_dhclient_clientid_vendorclassid_request_parameters(self):
        """ verify dhclient sends custom client-id, vendorclass and request parameters"""

        self.StartDnsMasq()
        self.StartCaptureBootpPackets()

        time.sleep(3)

        self.StartDhClient()

        time.sleep(10)
        self.StopCapturingPackets()
        time.sleep(3)

        output=subprocess.check_output(['ip','address', 'show', 'veth-test']).rstrip().decode('utf-8')

        # Address prefix
        self.assertRegex(output, "192.168.111.*")

        host='Host Name:.*%s' % socket.gethostname()
        self.FindProtocolFieldsinTCPDump(vendor_class='Vendor class identifier: Zeus_dhclient_vendorclass_id',
                                         client_mac_address='Client MAC address:.*\(02:01:02:03:04:08\)',
                                         host_name=host,
                                         client_identifier='\\\\021\\\\021\\\\022\\\\022\\\\023\\\\023\\\\024\\\\024\\\\025\\\\025\\\\026\\\\026',
                                         req_param1='Parameter Request List Item: \(1\) Subnet Mask',
                                         req_param28='Parameter Request List Item: \(28\) Broadcast Address',
                                         req_param2='Parameter Request List Item: \(2\) Time Offset',
                                         req_param3='Parameter Request List Item: \(3\) Router',
                                         req_param15='Parameter Request List Item: \(15\) Domain Name',
                                         req_param6='Parameter Request List Item: \(6\) Domain Name Server',
                                         req_param119='Parameter Request List Item: \(119\) Domain Search',
                                         req_param12='Parameter Request List Item: \(12\) Host Name',
                                         req_param44='Parameter Request List Item: \(44\) NetBIOS over TCP/IP Name Server',
                                         req_param47='Parameter Request List Item: \(47\) NetBIOS over TCP/IP Scope',
                                         req_param26='Parameter Request List Item: \(26\) Interface MTU',
                                         req_param121='Parameter Request List Item: \(121\) Classless Static Route',
                                         req_param42='Parameter Request List Item: \(42\) Network Time Protocol Servers')
        os.remove(DHCLIENT_TCP_DUMP_FILE)

    def test_dhclient_sets_dns_domain(self):
        """ dhclient request DNS and domain name and sets to resolv.conf """

        self.StartDnsMasq()

        time.sleep(1)

        self.StartDhClient()

        time.sleep(5)

        output=subprocess.check_output(['ip','address', 'show', 'veth-test']).rstrip().decode('utf-8')

        # Address prefix
        self.assertRegex(output, "192.168.111.*")

        # Default route
        output=subprocess.check_output(['ip','route', 'show', 'dev', 'veth-test']).rstrip().decode('utf-8')
        self.assertRegex(output, "default via 192.168.1.1*")

        # search example-test.com\nnameserver 8.8.8.8\nnameserver 8.8.4.4\n'
        # resolv.conf has configs
        self.SearchWordsInFile(RESOLV_CONF,
                               domain_name='search example-test.com',
                               nnameserver1='nameserver 8.8.8.8',
                               nnameserver2='nameserver 8.8.4.4')

    def test_dhclient_sets_mtu(self):
        """ dhclient gets MTU 1400 """

        self.StartDnsMasq()

        time.sleep(1)

        self.StartDhClient()

        time.sleep(5)

        output=subprocess.check_output(['ip','address', 'show', 'veth-test']).rstrip().decode('utf-8')

        # Address prefix
        self.assertRegex(output, "192.168.111.*")
        # MTU
        self.assertRegex(output, 'mtu 1400')

    def test_dhclient_ipv4(self):
        """ dhclient gets address """

        self.StartDnsMasq()

        time.sleep(1)

        self.StartDhClient()

        time.sleep(5)
        output=subprocess.check_output(['ip','address', 'show', 'veth-test']).rstrip().decode('utf-8')

        # Address prefix
        self.assertRegex(output, "192.168.111.*")

        # Default route
        output=subprocess.check_output(['ip','route', 'show', 'dev', 'veth-test']).rstrip().decode('utf-8')
        self.assertRegex(output, "default via 192.168.1.1*")


if __name__ == '__main__':
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,
                                                     verbosity=3))
