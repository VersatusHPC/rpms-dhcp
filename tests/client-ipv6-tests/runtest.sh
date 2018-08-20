#!/bin/bash
# SPDX-License-Identifier: LGPL-2.1+
# ~~~
#   runtest.sh of dhclient
#   Description: a  DHCPv6 client.
#
#   Author: Susant Sahani <susant@redhat.com>
#   Copyright (c) 2018 Red Hat, Inc.
# ~~~

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

PACKAGE_DHCLIENT="dhcp-client"
PACKAGE_RADVD="radvd"
PACKAGE_DHCP6S="wide-dhcpv6"

DHCLIENT_CI_DIR="/var/run/dhclient-ci"
RESOLVE_CONF="/etc/resolv.conf"

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm $PACKAGE_DHCLIENT
        rlAssertRpm $PACKAGE_RADVD
        rlAssertRpm $PACKAGE_DHCP6S

        rlFileBackup $RESOLVE_CONF

        rlRun "systemctl stop firewalld" 0,5
        rlRun "setenforce 0" 0,1

        rlRun "[ -e /sys/class/net/veth-test ] && ip link del veth-test" 0,1
        rlRun "cp dhclient-tests.py /usr/bin/"

        rlRun "mkdir -p $DHCLIENT_CI_DIR"
        rlRun "cp *.conf $DHCLIENT_CI_DIR"
    rlPhaseEnd

    rlPhaseStartTest
        rlLog "Starting dhclient tests ..."
        rlRun "/usr/bin/python3 /usr/bin/dhclient-tests.py"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "rm /usr/bin/dhclient-tests.py"
        rlFileRestore

        rlRun "[ -e /sys/class/net/veth-test ] && ip link del veth-test" 0,1

        rlRun "rm -rf $DHCLIENT_CI_DIR"
        rlRun "setenforce 1" 0,1

        rlLog "dhclient tests done"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd

rlGetTestState
