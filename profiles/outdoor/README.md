# Testing KaiAir on ARA (Outdoor)

## Introduction

These two [Heat Orchestration Templates (HOTs)](https://docs.openstack.org/heat/latest/template_guide/index.html)
by [ICICLE](https://icicle.ai) bootstrap the [Zun](https://docs.openstack.org/zun/latest/index.html)
containers necessary to test KaiAir on [ARA](https://arawireless.org)'s
outdoor radio access network (AraRAN) platform. `AraRAN-BaseStation-000.yaml`
launches the KaiAir-enabled [OCUDU](https://ocudu.org) gNodeB (gNB) base
station, while `AraRAN-UserEquipment-XXX.yaml` can be used to launch either
a commercial off-the-shelf (COTS) or OpenAirInterface (OAI) 5G New Radio
User Equipment (nrUE). Note, however, a COTS UE only works for the uplink
(UL) direction and for CQI-based downlink (DL). The full DL 
true-[SINR](https://en.wikipedia.org/wiki/Signal-to-interference-plus-noise_ratio)
loop requires the patched OAI nrUE.

## Before You Begin

These HOTs are modified versions of the
[`SSH.yaml`](https://gitlab.com/aralab/opera/opera-backbone/ara-generic-profiles/-/tree/master/ssh)
available as part of the ARA team's Open-Source Ecosystem for Broadband
Prairie (OPERA) project on GitLab. So, if you have not yet completed the
setup for `SSH.yaml`, please complete the instructions outlined in its
[README.md](https://gitlab.com/aralab/opera/opera-backbone/ara-generic-profiles/-/tree/master/ssh)
before you begin to use the HOTs provided here.

# Getting Started

You'll first need to check the availability of the AraRAN base
stations (BSs) and UEs where you plan to run KaiAir. The primary
requirement here is that the selected BS and UEs must support an
outdoor OCUDU deployment. You can find a list of OCUDU-compatible BSs
and their corresponding UEs in the [ARA User User Manual](https://arawireless.readthedocs.io/en/latest/). 
In particular, you'll want to review the [OCUDU Prototyping with O-RAN Compliant nearRT-RIC and xApps](https://arawireless.readthedocs.io/en/latest/ara_experiments/araran_experiments/ORAN_OCUDU_FlexRIC_xApp.html)
and [OCUDU with OpenAirInterface nrUE](https://arawireless.readthedocs.io/en/latest/ara_experiments/araran_experiments/ORAN_OCUDU_OAI_nrUE.html) experiments.

To check the current availablity of BSs and UEs, login to the
[ARA Portal](http://portal.arawireless.org) and navigate to and click on
the **Project > Reservations > Leases** menu tabs on the left-hand side
of the dashboard. Once there, locate and click on the **Host Calendar**
button in the upper right-hand side of the page. This lease calendar
shows all active leases on ARA resources. You can also cross-check these
leases against the status of each resource reported on the
[Resource Overview](https://portal.arawireless.org/project) page. Note,
however, the overview status tends to be less accurate than the lease
calendar.

## Launch OCUDU Base Station

Once you've selected a BS and confirmed its availability, you can proceed
with launching the KaiAir-enabled OCUDU gNB using the `AraRAN-BaseStation-000.yaml`
HOT. Navigate to and click on the **Project > Orchestration > Stacks** 
menu tabs on the left-hand side of the ARA Portal dashboard. With the *Stacks* page
open, click the **+Launch Stack** button on the right-hand side to pop-up
the **Select Profile** window.

In the **Select Profile** window, leave the **Profile Source** set to
*File* and then click on the **Choose File** button. Find your copy of 
the `AraRAN-BaseStation-000.yaml` HOT and select this as your 
**Profile File**. Once the HOT is selected, click the **Next** button.

You should now see the **Launch Stack** window. It should display three
input string parameter fields

  - **Stack Name**
  - **Login Username**
  - **SSH Public Key**

followed by five drop-down list parameters

  - **ARA Site Name**
  - **ARA Resource Type**
  - **ARA Device Type**
  - **ARA Device ID**
  - **ARA Container Image**

and then two input numbers parameter fields

  - **CPUs**
  - **Memory**

followed by two additional drop-down list parameters

  - **ARA Network**
  - **ARA Subnet**

and, finally, the one IP address

- **gNB SDR Interface IP Address**

Confirm that all input parameter values correctly reflect any prior
modifications to the HOT and then add a descriptive **Stack Name**. If
you need to make any other modficications, please do so before you click
the **Launch** button. In particular, make sure that you choose the correct 
**ARA Site Name** for your BS and set the **gNB SDR Interface IP Address**
to match the sector antenna that provides coverage for your target UE(s).

If the stack launch completes successfully, navigate to the
**Project > Container > Containers** page. Once there, click on link to
the container **Name** for the *AraRAN_BaseStation_000*. You can then
monitor the bootstrapping process for the container via the **Console** 
menu tab. The container is ready for testing once you see the `sshd` service 
restart successfully, the Universal Software Radio Peripheral (USRP) 
Hardware Driver (UHD) reports report back that the radios are connected, 
and the `KaiAir agent [gnb]` is running on port `5000`.

```
...
 * Restarting OpenBSD Secure Shell server sshd                           [ OK ]                                                             
[INFO] [UHD] linux; GNU C++ version 13.3.0; Boost_108300; UHD_4.7.0.HEAD-0-ga5ed1872                                                        
--------------------------------------------------                                                                                          
-- UHD Device 0                                                                                                                             
--------------------------------------------------                                                                                          
Device Address:                                                                                                                             
    serial: 31A8F56                                                                                                                         
    addr: 192.168.40.2                                                                                                                      
    fpga: XG                                                                                                                                
    name:                                                                                                                                   
    product: X310                                                                                                                           
    type: x300                                                                                                                              
--------------------------------------------------                                                                                          
-- UHD Device 1                                                                                                                             
--------------------------------------------------                                                                                          
Device Address:                                                                                                                             
    serial: 335FEAC                                                                                                                         
    addr: 192.168.20.2                                                                                                                      
    claimed: False                                                                                                                          
    fpga: HG                                                                                                                                
    mgmt_addr: 192.168.20.2                                                                                                                 
    name: ni-n3xx-335FEAC                                                                                                                   
    product: n320                                                                                                                           
    type: n3xx                                                                                                                              
--------------------------------------------------                                                                                          
-- UHD Device 2                                                                                                                             
--------------------------------------------------                                                                                          
Device Address:                                                                                                                             
    serial: 335FEAF                                                                                                                         
    addr: 192.168.30.2                                                                                                                      
    claimed: False                                                                                                                          
    fpga: HG                                                                                                                                
    mgmt_addr: 192.168.30.2                                                                                                                 
    name: ni-n3xx-335FEAF                                                                                                                   
    product: n320                                                                                                                           
    type: n3xx                                                                                                                              
KaiAir agent [gnb] on :5000  ctrl=/tmp/kaiair_ctrl.json
```

## Testing the KaiAir gNB Agent

Once the BS container is ready for testing, click on to the **Overview**
tab and find the *Floating IP Address* under the container *Spec*. Use 
this IP address to login to the container via the [ARA Jump Box](https://arawireless.readthedocs.io/en/latest/getting_started/ara_portal_extras.html#ara-jumpbox).

```
mkandes@hardtack:~$ ssh -J mckandes@jbox.arawireless.org icicle@10.189.10.133
Welcome to Ubuntu 24.04.1 LTS (GNU/Linux 5.4.0-216-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

This system has been minimized by removing packages and content that are
not required on a system that users do not log into.

To restore this content, you can run the 'unminimize' command.

The programs included with the Ubuntu system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Ubuntu comes with ABSOLUTELY NO WARRANTY, to the extent permitted by
applicable law.

To run a command as administrator (user "root"), use "sudo <command>".
See "man sudo_root" for details.

icicle@AgronomyFarm-BaseStation-000:~$
```

First, get the current status of the agent.

```
icicle@AgronomyFarm-BaseStation-000:~$ curl -w '\n' -X GET localhost:5000/health
{"role": "gnb", "online": true, "running": false}
icicle@AgronomyFarm-BaseStation-000:~$
```

Next, get the current state of KaiAir.

```
icicle@AgronomyFarm-BaseStation-000:~$ curl -w '\n' -X GET localhost:5000/kaiair/state
{"codesign": false, "power_control": false, "sinr_target_db": 10.0, "dl_sinr_target_db": 10.0, "ldp_deadline_ms": 0.0, "er_gate": "observe", "scheduler": "pf", "ul_power_apply": false}
icicle@AgronomyFarm-BaseStation-000:~$
```

When ready, start the gNB and confirm it is running successfully.

```
icicle@AgronomyFarm-BaseStation-000:~$ curl -w '\n' -X POST localhost:5000/gnb/start
{"ok": true, "msg": "started"}
icicle@AgronomyFarm-BaseStation-000:~$
```

```
icicle@AgronomyFarm-BaseStation-000:~$ curl -w '\n' -X GET localhost:5000/health
{"role": "gnb", "online": true, "running": true}
icicle@AgronomyFarm-BaseStation-000:~$
```

If the gNB starts up successfully and connects to the Access and Mobility 
Management Function (AMF) in the core network, you should see the 
following in the `kaiair_gnb.log` file.

```
icicle@AgronomyFarm-BaseStation-000:~$ cat /var/log/kaiair_gnb.log

--== OCUDU gNB (commit ac812fde52) ==--

Lower PHY in triple executor mode.
TDD cell detected: forcing radio tx_mode to 'discontinuous' so the RF front-end follows the TDD pattern. Set tx_mode explicitly to override.
Available radio types: uhd and zmq.
[INFO] [UHD] linux; GNU C++ version 13.3.0; Boost_108300; UHD_4.7.0.HEAD-0-ga5ed1872
Making USRP object with args 'type=n3xx,addr=192.168.20.2,master_clock_rate=245.76e6,send_frame_size=8000,recv_frame_size=8000'
Setting FP0 GPIO for TDD RF front-end on uhd_n300.
Aligning TX power ramping guard time to the UHD buffer size, i.e., 1996. Aligned guard time: 0.0 us.
Cell pci=1, bw=40 MHz, 1T1R, dl_arfcn=629334 (n78), dl_freq=3440.01 MHz, dl_ssb_arfcn=628320, ul_freq=3440.01 MHz

N2: Connection to AMF on 10.189.8.8:38412 completed
==== gNB started ===
Type <h> to view help
icicle@AgronomyFarm-BaseStation-000:~$
```

Check the latest telemetry metrics.

```
icicle@AgronomyFarm-BaseStation-000:~$ curl -w '\n' -X GET localhost:5000/metrics
{"ts": 1792184166.415, "pci": 1, "actuate": false, "ldp_on": false, "ldp_deadline_ms": 10.0, "ldp_pkt_beta": 0.9, "store_reports": 0, "store_ues": 0, "ssb_dbm": 16.0, "er_gate": "observe", "peer_cells": 0, "peer_links": 0, "gate_muted": 0, "gate_allowed": 0, "links": [], "rnti": null, "ul_sinr_db": null, "ul_rsrp_dbfs": null, "ni_dbfs": null, "e_max_dbfs": null, "tpc_db": null, "dl_cqi": null, "dl_bler_pct": null, "ul_delay_ms": null, "k_db": null, "er_nodes": null, "ul_mbps": null, "dl_mbps": null, "eco_ratio": null, "ldp_dl_tbs": null, "ldp_dl_ontime_pct": null, "ldp_dl_late_pct": null, "ldp_dl_failed_pct": null, "ldp_dl_avg_tx": null, "ldp_ul_tbs": null, "ldp_ul_ontime_pct": null, "ldp_ul_late_pct": null, "ldp_ul_failed_pct": null, "ldp_ul_avg_tx": null, "dl_sinr_true_db": null, "dl_sinr_target_db": null, "dl_gamma_db": null, "dl_pwr_shed_db": null, "source": "live"}
icicle@AgronomyFarm-BaseStation-000:~$
```

To use the agent's web dashboard, start the server

```
icicle@AgronomyFarm-BaseStation-000:~$ sudo -i
root@AgronomyFarm-BaseStation-000:~# python3 kaiair/dashboard/kaiair_dash.py 
KaiAir dashboard: http://localhost:8080  (bench host: gnb1 via ssh)
```

and then create an SSH tunnel to the container.

```
mkandes@hardtack:~$ ssh -J mckandes@jbox.arawireless.org -L 8080:localhost:8080 icicle@10.189.10.133 -N
```

Once the dashboard server is running and the tunnel is created, open
your web broswer and navigate to [http://localhost:8080](http://localhost:8080).

## Launch COTS User Equipment

Once the gNB is running, go ahead and launch the `AraRAN-UserEquipment-XXX.yaml` HOT.

*To be continued ...*

## Launch OAI User Equipment

Once the gNB is running, go ahead and launch the `AraRAN-UserEquipment-XXX.yaml` HOT.

*To be continued ...*

## Common Failure Modes

```
BlazarClientException: resources.lease_0: ERROR: Start date must be later than current date
```

Delete stack. Relaunch once failed stack has cleared.

```
Resource CREATE failed: ResourceInError: resources.container_0: Went to status Error due to "Error in creating container 'container_0' - There are not enough hosts available."

```

```
Docker internal error: 409 Client Error for http://10.188.33.36:2375/v1.26/containers/a5e9f8037196fdc80c5d5bf32c28264cfa3cec046091149aa67c358ae916a5f9?v=False&link=False&force=False: Conflict ("You cannot remove a running container a5e9f8037196fdc80c5d5bf32c28264cfa3cec046091149aa67c358ae916a5f9. Stop the container before attempting removal or force remove").
```

```
Resource CREATE failed: NotFound: resources.container_0: Container afbbbe66-eec3-4baf-8985-33335708701f could not be found. (HTTP 404) (Request-ID: req-21a3b254-9334-4a78-8d3b-8b027cb9f5e8)

```

# Acknowledgements

This material is based upon work supported by the [U.S. National Science Foundation](https://www.nsf.gov)
under [Award No. CISE/OAC-2112606](https://www.nsf.gov/awardsearch/show-award/?AWD_ID=2112606).
Any opinions, findings, conclusions, or recommendations expressed in this
material are those of the authors and do not necessarily reflect the views
of the NSF.

<img src='https://nsf.widen.net/content/josuwjrmy6/png/NSF_Official_logo_Med_Res_600ppi.png' alt='NSF Logo' width='250'/>
