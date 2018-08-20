#!/bin/bash
# SPDX-License-Identifier: LGPL-2.1+
# ~~~
#   runtest.sh of dhclient
#   Description:  dhclient - Dynamic Host Configuration Protocol Client.
#
#   Author: Susant Sahani <susant@redhat.com>
#   Copyright (c) 2018 Red Hat, Inc.
# ~~~

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

PACKAGE="dhcp-client"

DHCLIENT_CI_DIR="/var/run/dhclient-ci"
RESOLVE_CONF="/etc/resolv.conf"

rlJournalStart
    rlPhaseStartSetup
        rlAssertRpm $PACKAGE

        rlRun "systemctl stop firewalld" 0,5
        rlRun "setenforce 0" 0,1
        rlFileBackup "$RESOLVE_CONF"

        rlRun "[ -e /sys/class/net/veth-test ] && ip link del veth-test" 0,1

        rlRun "cp dhclient-tests.py /usr/bin/"
        rlRun "cp tsharkd.service /var/run/systemd/system"

        rlRun "mkdir -p $DHCLIENT_CI_DIR"
        rlRun "cp *.conf $DHCLIENT_CI_DIR"
        rlRun "systemctl daemon-reload"
    rlPhaseEnd

    rlPhaseStartTest
        rlLog "Starting dhclient tests ..."
        rlRun "/usr/bin/python3 /usr/bin/dhclient-tests.py"
    rlPhaseEnd

    rlPhaseStartCleanup
        rlRun "rm /usr/bin/dhclient-tests.py /var/run/systemd/system/tsharkd.service"
        rlrun "rm -rf $DHCLIENT_CI_DIR"

        rlRun "setenforce 1" 0,1
        rlRun "systemctl daemon-reload"
        rlRun "[ -e /sys/class/net/veth-test ] && ip link del veth-test" 0,1
        rlFileRestore
        rlLog "dhclient tests done"
    rlPhaseEnd
rlJournalPrintText
rlJournalEnd

rlGetTestState
