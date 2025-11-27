# rpms-dhcp

This repository contains the removed `dhcpd` package spec for Enterprise Linux 10 and it's variants.

# Build instructions

1. Install required packages:

```
# dnf -y groupinstall "Development Tools"
# dnf -y install mock rpmdevtools
```

2. Clone this git repository:

```
# git clone https://github.com/VersatusHPC/rpms-dhcp.git
```

3. Start the build process and generate the SRPM and RPM packages:

```
# cd rpms-dhcp
# mkdir build
# rpmdev-spectool --get-files --sources ./dhcp.spec
# mock -r rhel-10-x86_64 --buildsrpm --spec ./dhcp.spec --sources . --resultdir ./build/SRPMS
# mock -r rhel-10-x86_64 --rebuild ./build/SRPMS/*.src.rpm --resultdir ./build/RPMS
```

4. Move the SRPM/RPM packages to the final destination. They are found on `./build`.

